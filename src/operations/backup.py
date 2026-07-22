from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class BackupRestoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BackupFile:
    path: Path
    sha256: str
    size_bytes: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_manifest(root: Path) -> dict[str, dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        raise BackupRestoreError(f"artifact root does not exist: {root}")
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        manifest[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return manifest


class BackupRestoreManager:
    def __init__(
        self,
        *,
        database_url: str,
        environment: str,
        command_environment: Mapping[str, str] | None = None,
    ) -> None:
        if environment not in {"staging", "production"}:
            raise ValueError("environment must be staging or production")
        self.database_url = database_url
        self.environment = environment
        self.command_environment = {
            **os.environ,
            **dict(command_environment or {}),
        }

    def create_database_backup(self, destination: Path) -> BackupFile:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "pg_dump",
                "--dbname",
                self.database_url,
                "--format=custom",
                "--compress=6",
                "--no-owner",
                "--no-privileges",
                "--schema=football_brief",
                "--file",
                str(destination),
            ],
            safe_label="pg_dump football_brief",
        )
        return self._backup_file(destination)

    def restore_database_backup(
        self,
        backup: Path,
        *,
        expected_sha256: str,
        allow_destructive_drill: bool,
    ) -> BackupFile:
        verified = self._verify_backup(backup, expected_sha256)
        if self.environment == "production":
            raise BackupRestoreError(
                "direct production restore is disabled; restore into an isolated database and follow the runbook"
            )
        if not allow_destructive_drill:
            raise BackupRestoreError("database restore requires allow_destructive_drill=True")
        self._run(
            [
                "psql",
                "--dbname",
                self.database_url,
                "--set",
                "ON_ERROR_STOP=1",
                "--command",
                "DROP SCHEMA IF EXISTS football_brief CASCADE;",
            ],
            safe_label="drop staging football_brief schema",
        )
        self._run(
            [
                "pg_restore",
                "--dbname",
                self.database_url,
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                str(backup),
            ],
            safe_label="pg_restore football_brief",
        )
        return verified

    def create_artifact_backup(self, root: Path, destination: Path) -> tuple[BackupFile, dict[str, Any]]:
        manifest = artifact_manifest(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            destination,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            )
            for relative in sorted(manifest):
                archive.write(root / relative, arcname=f"objects/{relative}")
        return self._backup_file(destination), manifest

    def restore_artifact_backup(
        self,
        backup: Path,
        destination: Path,
        *,
        expected_sha256: str,
        allow_destructive_drill: bool,
    ) -> dict[str, Any]:
        self._verify_backup(backup, expected_sha256)
        if self.environment == "production":
            raise BackupRestoreError(
                "direct production artifact restore is disabled; restore into an isolated path and follow the runbook"
            )
        if not allow_destructive_drill:
            raise BackupRestoreError("artifact restore requires allow_destructive_drill=True")
        with zipfile.ZipFile(backup, mode="r") as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise BackupRestoreError("artifact backup manifest is missing")
            expected_manifest = json.loads(archive.read("manifest.json"))
            expected_names = {f"objects/{relative}" for relative in expected_manifest}
            if names - {"manifest.json"} != expected_names:
                raise BackupRestoreError("artifact backup members do not match the manifest")
            temporary = destination.with_name(f"{destination.name}.restore-tmp")
            if temporary.exists():
                shutil.rmtree(temporary)
            temporary.mkdir(parents=True)
            for relative in sorted(expected_manifest):
                source_name = f"objects/{relative}"
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(source_name) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
            restored_manifest = artifact_manifest(temporary)
            if restored_manifest != expected_manifest:
                shutil.rmtree(temporary, ignore_errors=True)
                raise BackupRestoreError("restored artifact manifest does not match the backup")
            if destination.exists():
                shutil.rmtree(destination)
            temporary.replace(destination)
        return {
            "manifest": expected_manifest,
            "object_count": len(expected_manifest),
            "total_bytes": sum(int(item["size_bytes"]) for item in expected_manifest.values()),
        }

    def verify_database_schema(self, expected_migration_head: str) -> dict[str, Any]:
        completed = self._run(
            [
                "psql",
                "--dbname",
                self.database_url,
                "--tuples-only",
                "--no-align",
                "--set",
                "ON_ERROR_STOP=1",
                "--command",
                "SELECT filename FROM football_brief.schema_migrations ORDER BY applied_at DESC,filename DESC LIMIT 1;",
            ],
            safe_label="verify restored migration head",
            capture_output=True,
        )
        actual = completed.stdout.strip()
        if actual != expected_migration_head:
            raise BackupRestoreError(
                f"restored migration head mismatch: expected {expected_migration_head}, got {actual or '<empty>'}"
            )
        return {"expected_migration_head": expected_migration_head, "actual_migration_head": actual}

    def _run(
        self,
        command: list[str],
        *,
        safe_label: str,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                env=self.command_environment,
                check=True,
                text=True,
                capture_output=capture_output,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise BackupRestoreError(f"required PostgreSQL client is unavailable during {safe_label}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip().splitlines()
            safe_error = stderr[-1][:500] if stderr else "command failed"
            raise BackupRestoreError(f"{safe_label} failed: {safe_error}") from exc
        except subprocess.TimeoutExpired as exc:
            raise BackupRestoreError(f"{safe_label} timed out") from exc

    @staticmethod
    def _backup_file(path: Path) -> BackupFile:
        if not path.exists() or path.stat().st_size <= 0:
            raise BackupRestoreError(f"backup was not created: {path}")
        return BackupFile(path=path, sha256=sha256_file(path), size_bytes=path.stat().st_size)

    @staticmethod
    def _verify_backup(path: Path, expected_sha256: str) -> BackupFile:
        backup = BackupRestoreManager._backup_file(path)
        if backup.sha256 != expected_sha256:
            raise BackupRestoreError(
                f"backup checksum mismatch for {path.name}: expected {expected_sha256}, got {backup.sha256}"
            )
        return backup
