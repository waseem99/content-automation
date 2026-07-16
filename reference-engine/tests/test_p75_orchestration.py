import json
from pathlib import Path

from refintel.models import (
    Platform,
    ProjectStatus,
    ReferenceProject,
    RightsDeclaration,
    SourceAccess,
    SourceDescriptor,
)
from refintel.orchestration import (
    EXECUTION_PROFILES,
    ExecutionProfileName,
    PortfolioRunRequest,
    ReferenceRunInput,
    run_portfolio,
    safe_source_label,
    write_request_template,
)


class FakePipeline:
    def __init__(self, root: Path, *, fail_names: set[str] | None = None) -> None:
        self.root = root
        self.fail_names = fail_names or set()
        self.process_options: list[dict[str, object]] = []

    def ingest_file(self, source_path: str, **kwargs: object) -> ReferenceProject:
        source = Path(source_path)
        if source.name in self.fail_names:
            raise RuntimeError(f"token=private failed at {source}")
        workspace = self.root / f"ref-{source.stem}"
        (workspace / "frames").mkdir(parents=True, exist_ok=True)
        (workspace / "frames" / "contact_sheet.jpg").write_bytes(b"review-only")
        return ReferenceProject(
            reference_id=f"ref-{source.stem}",
            status=ProjectStatus.INGESTED,
            source=SourceDescriptor(
                kind="file",
                platform=Platform.LOCAL,
                original_path=str(source),
                title=str(kwargs.get("title") or source.stem),
                canonical_key=f"fixture:{source.stem}",
            ),
            access=SourceAccess(declaration=kwargs["rights"]),
            workspace_path=str(workspace),
        )

    def ingest_url(self, url: str, **kwargs: object) -> ReferenceProject:
        raise AssertionError(f"unexpected live URL in offline test: {url} {kwargs}")

    def process(self, reference_id: str, **kwargs: object) -> ReferenceProject:
        self.process_options.append(kwargs)
        source = self.root.parent / f"{reference_id.removeprefix('ref-')}.mp4"
        return self.ingest_file(source, rights=RightsDeclaration.PERMITTED)

    def export_brief(self, reference_id: str, **kwargs: object) -> Path:
        target = self.root / reference_id / "exports" / "original_content_brief.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(kwargs), encoding="utf-8")
        return target


def test_profiles_are_explicit_and_do_not_claim_hosted_processing() -> None:
    assert set(EXECUTION_PROFILES) == {
        ExecutionProfileName.CPU,
        ExecutionProfileName.GPU,
        ExecutionProfileName.LOW_MEMORY,
    }
    assert EXECUTION_PROFILES[ExecutionProfileName.GPU].transcription_device == "cuda"
    assert EXECUTION_PROFILES[ExecutionProfileName.CPU].local_vision is False
    assert EXECUTION_PROFILES[ExecutionProfileName.LOW_MEMORY].every_frame is False


def test_portfolio_run_isolates_failures_and_redacts_local_data(tmp_path: Path) -> None:
    good = tmp_path / "good.mp4"
    bad = tmp_path / "bad.mp4"
    good.write_bytes(b"good-source")
    bad.write_bytes(b"bad-source")
    request = PortfolioRunRequest(
        profile=ExecutionProfileName.CPU,
        references=[
            ReferenceRunInput(source=str(good), rights=RightsDeclaration.PERMITTED),
            ReferenceRunInput(source=str(bad), rights=RightsDeclaration.PERMITTED),
        ],
    )
    fake = FakePipeline(tmp_path / "workspace", fail_names={"bad.mp4"})

    manifest, target = run_portfolio(request, tmp_path / "workspace", pipeline=fake)
    rendered = target.read_text(encoding="utf-8")

    assert manifest.status == "partial"
    assert manifest.succeeded == 1
    assert manifest.failed == 1
    assert "ingest-file" in manifest.results[1].fallback_action
    assert "<redacted>" in rendered
    assert str(tmp_path) not in rendered
    assert "good-source" not in rendered
    assert manifest.source_media_in_manifest is False
    assert manifest.credentials_in_manifest is False
    assert manifest.automatic_publication is False
    assert manifest.human_review_required is True
    assert fake.process_options[0]["transcription_device"] == "cpu"


def test_source_labels_and_request_template_are_safe(tmp_path: Path) -> None:
    source = tmp_path / "private-name.mp4"
    source.write_bytes(b"fixture")
    assert safe_source_label("https://user:pass@youtube.com/watch?v=abc&token=secret") == (
        "https://youtube.com/watch?v=abc"
    )
    label = safe_source_label(str(source))
    assert label.startswith("local-file:")
    assert "private-name" not in label

    target = write_request_template(tmp_path / "request.json")
    payload = json.loads(target.read_text())
    assert payload["continue_on_error"] is True
    assert payload["profile"] == "cpu"
    assert "password" not in target.read_text().lower()
