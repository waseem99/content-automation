from __future__ import annotations

import hmac
from uuid import UUID

from src.application.shared_storage.providers import SharedAccessTarget
from src.application.shared_storage.service import (
    SharedArtifactError,
    _json,
    _utcnow,
)
from src.application.shared_storage.validated_service import ValidatedSharedArtifactService
from src.application.shared_storage.providers import token_digest


class AuditedSharedArtifactService(ValidatedSharedArtifactService):
    """Validated service that commits both successful and denied access events."""

    def consume_access(
        self,
        *,
        grant_id: UUID,
        token: str,
        remote_address: str | None = None,
        user_agent: str | None = None,
    ) -> SharedAccessTarget:
        digest = token_digest(token)
        error_code = None
        backend = None
        object_key = None
        mime_type = None
        filename = None
        remaining = 0
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT sag.*,sav.status AS artifact_status,sso.object_key,
                          sso.status AS object_status,sso.mime_type,a.original_filename,ssb.*
                   FROM football_brief.shared_access_grants sag
                   JOIN football_brief.shared_artifact_versions sav ON sav.id=sag.artifact_version_id
                   JOIN football_brief.shared_storage_objects sso ON sso.id=sag.storage_object_id
                   JOIN football_brief.assets a ON a.id=sso.asset_id
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE sag.id=%s FOR UPDATE OF sag""",
                (grant_id,),
            ).fetchone()
            if not row:
                raise SharedArtifactError("access_grant_not_found")
            event = "accessed"
            if not hmac.compare_digest(str(row["token_digest"]), digest):
                event, error_code = "denied", "access_token_invalid"
            elif row["revoked_at"] is not None:
                event, error_code = "denied", "access_grant_revoked"
            elif row["expires_at"] <= _utcnow():
                event, error_code = "expired", "access_grant_expired"
            elif row["artifact_status"] == "deleted" or row["object_status"] != "available":
                event, error_code = "denied", "shared_object_unavailable"
            elif row["status"] != "active":
                event, error_code = "denied", "shared_backend_unavailable"
            conn.execute(
                """INSERT INTO football_brief.shared_access_events
                   (grant_id,event,remote_address_hash,user_agent_hash,details)
                   VALUES (%s,%s,%s,%s,%s::jsonb)""",
                (
                    grant_id,
                    event,
                    self._optional_digest(remote_address),
                    self._optional_digest(user_agent),
                    _json({"error_code": error_code} if error_code else {"backend_key": row["backend_key"]}),
                ),
            )
            backend = dict(row)
            object_key = row["object_key"]
            mime_type = row["mime_type"]
            filename = row["original_filename"]
            remaining = max(1, int((row["expires_at"] - _utcnow()).total_seconds()))

        if error_code:
            raise SharedArtifactError(error_code)
        provider = self.providers.provider(backend)
        return provider.access_target(
            object_key=object_key,
            expires_in_seconds=min(remaining, 3600),
            mime_type=mime_type,
            filename=filename,
        )
