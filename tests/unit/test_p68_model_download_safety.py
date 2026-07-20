from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_model_download_starts_cleanly() -> None:
    script = (ROOT / "scripts/windows/download_p68_sdxl_preview_model.ps1").read_text(encoding="utf-8")
    assert "Remove-Item -Force $partialPath" in script
    assert "curl.exe -L --fail --retry 5 --retry-delay 5 --output $partialPath" in script
    assert "-C -" not in script
