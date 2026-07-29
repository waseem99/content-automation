from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from src.infrastructure.database.connection import Database


_STOP_WORDS = {
    "about", "after", "again", "also", "among", "because", "been", "before", "being",
    "between", "both", "could", "does", "during", "each", "from", "have", "into", "many",
    "more", "most", "other", "over", "same", "some", "such", "than", "that", "their",
    "there", "these", "they", "this", "those", "through", "under", "very", "what", "when",
    "where", "which", "while", "with", "would", "your",
}


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    rank: int
    title: str
    canonical_url: str
    snippet: str
    page_id: int
    match_score: float


class AutomaticScriptEvidenceService:
    """Best-effort evidence enrichment for newly generated working scripts.

    The service never fails script generation. It stores research lineage for every attempted
    factual claim and auto-attaches only a conservative Wikipedia match. Any claim that remains
    unresolved is left visible for review; a Super Admin may later approve it through the
    explicit audited override path.
    """

    endpoint = "https://en.wikipedia.org/w/api.php"
    user_agent = "ContentAutomationP111/1.0 (automatic local script evidence enrichment)"

    def __init__(self, database: Database) -> None:
        self.database = database
        self.claim_limit = max(1, min(20, int(os.getenv("LOCAL_AUTO_RESEARCH_CLAIM_LIMIT", "8"))))
        self.result_limit = max(1, min(5, int(os.getenv("LOCAL_AUTO_RESEARCH_RESULT_LIMIT", "3"))))
        self.minimum_match_score = max(
            0.20,
            min(0.90, float(os.getenv("LOCAL_AUTO_RESEARCH_MINIMUM_MATCH", "0.45"))),
        )

    def enrich(self, *, document_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.connection() as conn:
            document = conn.execute(
                """SELECT sd.id,sd.current_version_id,sd.lock_version,sv.status
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   WHERE sd.id=%s""",
                (document_id,),
            ).fetchone()
            if document is None or document["status"] != "working":
                return {
                    "attempted": 0,
                    "auto_attached": 0,
                    "unresolved": 0,
                    "skipped": "working_script_required",
                }
            claims = conn.execute(
                """SELECT sc.id,sc.claim_key,sc.claim_text,sc.support_status
                   FROM football_brief.script_claims sc
                   WHERE sc.script_version_id=%s
                     AND sc.claim_type='factual'
                     AND sc.support_status<>'supported'
                   ORDER BY sc.created_at,sc.id
                   LIMIT %s""",
                (document["current_version_id"], self.claim_limit),
            ).fetchall()

        attempted = 0
        attached = 0
        failures: list[dict[str, str]] = []
        for raw_claim in claims:
            claim = dict(raw_claim)
            attempted += 1
            try:
                if self._research_and_maybe_attach(
                    document_id=document_id,
                    script_version_id=UUID(str(document["current_version_id"])),
                    claim=claim,
                    actor=actor,
                ):
                    attached += 1
            except Exception as exc:  # best effort: script generation must still complete
                failures.append({"claim_id": str(claim["id"]), "error": f"{type(exc).__name__}: {exc}"[:500]})

        if attached:
            with self.database.transaction() as conn:
                conn.execute(
                    "UPDATE football_brief.script_documents SET lock_version=lock_version+1 WHERE id=%s",
                    (document_id,),
                )

        return {
            "attempted": attempted,
            "auto_attached": attached,
            "unresolved": max(0, attempted - attached),
            "failures": failures,
            "provider": "wikipedia",
            "automatic_approval": False,
        }

    def _research_and_maybe_attach(
        self,
        *,
        document_id: UUID,
        script_version_id: UUID,
        claim: dict[str, Any],
        actor: str,
    ) -> bool:
        query = str(claim["claim_text"]).strip()
        with self.database.transaction() as conn:
            run = conn.execute(
                """INSERT INTO football_brief.script_source_research_runs
                   (script_document_id,script_version_id,claim_id,query,provider,provider_model,status,
                    requested_by,retrieval_evidence)
                   VALUES (%s,%s,%s,%s,'wikipedia','mediawiki-search-v1','running',%s,%s::jsonb)
                   RETURNING *""",
                (
                    document_id,
                    script_version_id,
                    claim["id"],
                    query,
                    actor,
                    json.dumps({
                        "automatic": True,
                        "stage": "script_generation",
                        "claim_key": claim["claim_key"],
                    }),
                ),
            ).fetchone()

        try:
            candidates = self._search(query)
        except Exception as exc:
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.script_source_research_runs
                       SET status='failed',error_code=%s,completed_at=now(),
                           retrieval_evidence=retrieval_evidence || %s::jsonb
                       WHERE id=%s""",
                    (type(exc).__name__.lower(), json.dumps({"error": str(exc)[:500]}), run["id"]),
                )
            return False

        inserted: list[tuple[dict[str, Any], EvidenceCandidate]] = []
        with self.database.transaction() as conn:
            for candidate in candidates:
                digest = hashlib.sha256(
                    f"{candidate.title}\n{candidate.canonical_url}\n{candidate.snippet}".encode("utf-8")
                ).hexdigest()
                row = conn.execute(
                    """INSERT INTO football_brief.script_source_research_candidates
                       (research_run_id,rank,title,publisher,canonical_url,source_type,quality_score,
                        relevance_summary,evidence_locator,evidence_digest,rights_declaration,
                        permitted_use,metadata)
                       VALUES (%s,%s,%s,'Wikipedia',%s,'secondary',75,%s,%s,%s,
                               'publicly_accessible','Metadata and short evidence summary for editorial verification',%s::jsonb)
                       ON CONFLICT (research_run_id,canonical_url) DO NOTHING
                       RETURNING *""",
                    (
                        run["id"],
                        candidate.rank,
                        candidate.title,
                        candidate.canonical_url,
                        candidate.snippet or f"Wikipedia result for {candidate.title}",
                        f"Wikipedia page {candidate.page_id}",
                        digest,
                        json.dumps({
                            "automatic": True,
                            "match_score": candidate.match_score,
                            "page_id": candidate.page_id,
                        }),
                    ),
                ).fetchone()
                if row is not None:
                    inserted.append((dict(row), candidate))

            conn.execute(
                """UPDATE football_brief.script_source_research_runs
                   SET status=%s,result_count=%s,completed_at=now(),
                       retrieval_evidence=retrieval_evidence || %s::jsonb
                   WHERE id=%s""",
                (
                    "completed" if inserted else "no_results",
                    len(inserted),
                    json.dumps({
                        "retrieved_candidates": len(inserted),
                        "automatic_attachment_threshold": self.minimum_match_score,
                    }),
                    run["id"],
                ),
            )

        selected = next(
            (
                pair for pair in inserted
                if pair[1].match_score >= self.minimum_match_score
                and self._numbers_are_preserved(query, pair[1].title + " " + pair[1].snippet)
            ),
            None,
        )
        if selected is None:
            return False

        candidate_row, candidate = selected
        inspected = self._inspect_public_url(candidate.canonical_url)
        with self.database.transaction() as conn:
            current = conn.execute(
                """SELECT sd.current_version_id,sv.status
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   WHERE sd.id=%s FOR UPDATE OF sd,sv""",
                (document_id,),
            ).fetchone()
            if (
                current is None
                or UUID(str(current["current_version_id"])) != script_version_id
                or current["status"] != "working"
            ):
                return False

            source = conn.execute(
                """SELECT * FROM football_brief.script_sources
                   WHERE script_version_id=%s AND canonical_url=%s""",
                (script_version_id, inspected["final_url"]),
            ).fetchone()
            if source is None:
                source = conn.execute(
                    """INSERT INTO football_brief.script_sources
                       (script_version_id,source_key,source_type,title,publisher,canonical_url,
                        quality_score,rights_declaration,permitted_use,evidence_digest,notes)
                       VALUES (%s,%s,'secondary',%s,'Wikipedia',%s,75,'publicly_accessible',
                               'Metadata and short evidence summary for editorial verification',%s,%s)
                       RETURNING *""",
                    (
                        script_version_id,
                        f"auto-wiki-{str(candidate_row['id']).replace('-', '')[:12]}",
                        candidate.title,
                        inspected["final_url"],
                        inspected["sha256"],
                        "Automatically matched during local script generation; final editorial responsibility remains with the approving operator.",
                    ),
                ).fetchone()

            conn.execute(
                """INSERT INTO football_brief.script_claim_sources
                   (script_version_id,claim_id,source_id,support_type,locator,support_note)
                   VALUES (%s,%s,%s,'corroborating',%s,%s)
                   ON CONFLICT (claim_id,source_id,support_type) DO UPDATE SET
                     locator=EXCLUDED.locator,support_note=EXCLUDED.support_note""",
                (
                    script_version_id,
                    claim["id"],
                    source["id"],
                    f"Wikipedia page {candidate.page_id}",
                    "Automatically matched from a conservative Wikipedia result during local script generation.",
                ),
            )
            conn.execute(
                "UPDATE football_brief.script_claims SET support_status='supported' WHERE id=%s",
                (claim["id"],),
            )
            conn.execute(
                """UPDATE football_brief.script_source_research_candidates
                   SET validation_status='valid',validated_at=now(),accepted_by=%s,accepted_at=now(),
                       metadata=metadata || %s::jsonb
                   WHERE id=%s""",
                (
                    actor,
                    json.dumps({
                        "automatic_attachment": True,
                        "validated_final_url": inspected["final_url"],
                        "algorithm": "token-overlap-v1",
                    }),
                    candidate_row["id"],
                ),
            )
        return True

    def _search(self, query: str) -> list[EvidenceCandidate]:
        params = urlencode({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": self.result_limit,
            "format": "json",
            "utf8": 1,
            "origin": "*",
        })
        request = Request(
            f"{self.endpoint}?{params}",
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed Wikipedia endpoint
            payload = json.loads(response.read(512_000).decode("utf-8"))
        results = payload.get("query", {}).get("search", [])
        output: list[EvidenceCandidate] = []
        for index, item in enumerate(results, start=1):
            title = self._plain_text(str(item.get("title") or ""))
            snippet = self._plain_text(str(item.get("snippet") or ""))
            page_id = int(item.get("pageid") or 0)
            if not title or page_id <= 0:
                continue
            output.append(EvidenceCandidate(
                rank=index,
                title=title,
                canonical_url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                snippet=snippet,
                page_id=page_id,
                match_score=self._match_score(query, f"{title} {snippet}"),
            ))
        return output

    @staticmethod
    def _plain_text(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if len(token) >= 4 and token not in _STOP_WORDS
        }

    @classmethod
    def _match_score(cls, claim: str, evidence: str) -> float:
        claim_tokens = cls._tokens(claim)
        evidence_tokens = cls._tokens(evidence)
        if not claim_tokens or not evidence_tokens:
            return 0.0
        overlap = len(claim_tokens.intersection(evidence_tokens))
        denominator = max(3, min(len(claim_tokens), 10))
        return min(1.0, overlap / denominator)

    @staticmethod
    def _numbers_are_preserved(claim: str, evidence: str) -> bool:
        numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", claim))
        if not numbers:
            return True
        evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence))
        return numbers.issubset(evidence_numbers)

    @staticmethod
    def _assert_public_https_url(value: str) -> tuple[str, str]:
        parsed = urlparse(value.strip())
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("source_url_must_be_public_https")
        if parsed.username or parsed.password:
            raise ValueError("source_url_credentials_are_not_allowed")
        host = parsed.hostname.lower().rstrip(".")
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        for raw in addresses:
            ip = ipaddress.ip_address(raw)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise ValueError("private_source_host_not_allowed")
        return value.strip(), host

    def _inspect_public_url(self, value: str) -> dict[str, str]:
        safe_url, _ = self._assert_public_https_url(value)
        request = Request(
            safe_url,
            headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            with urlopen(request, timeout=12) as response:  # noqa: S310 - strict public HTTPS validation
                final_url = response.geturl()
                self._assert_public_https_url(final_url)
                raw = response.read(512_000)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"source_url_validation_failed: {exc}") from exc
        return {"final_url": final_url, "sha256": hashlib.sha256(raw).hexdigest()}


__all__ = ["AutomaticScriptEvidenceService", "EvidenceCandidate"]
