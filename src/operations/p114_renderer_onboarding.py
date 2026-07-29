from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


ROOT = Path(__file__).resolve().parents[2]
WAN_PROVIDER = "wan-ai"
WAN_MODEL = "Wan2.2-TI2V-5B"
HUNYUAN_PROVIDER = "tencent-hunyuan"
HUNYUAN_MODEL = "HunyuanVideo-1.5-480p-I2V-Step-Distilled"


def _true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _model_files(name: str) -> list[dict[str, str]]:
    raw = os.getenv(name, "[]").strip() or "[]"
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise RuntimeError(f"{name} must be a JSON array")
    result: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise RuntimeError(f"{name} entries must be objects")
        role = str(item.get("role") or "").strip()
        relative_path = str(item.get("relative_path") or "").strip().replace("\\", "/")
        digest = str(item.get("sha256") or "").strip().lower()
        if not role or not relative_path or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise RuntimeError(f"{name} entries require role, relative_path, and lowercase SHA-256")
        if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise RuntimeError(f"{name} relative_path must stay within the configured ComfyUI root")
        result.append({"role": role, "relative_path": relative_path, "sha256": digest})
    return result


class P114RendererOnboarding:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.actor = os.getenv("LOCAL_SUPER_ADMIN_OPERATOR_ID", "local-super-admin")
        self.worker_id = os.getenv("P114_LOCAL_VIDEO_WORKER_OPERATOR_ID", "p114-local-video-worker")

    def run(self) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_operator(conn, self.actor)
            self._ensure_worker(conn)
            wan_policy = self._policy(conn, WAN_PROVIDER, WAN_MODEL)
            hunyuan_policy = self._policy(conn, HUNYUAN_PROVIDER, HUNYUAN_MODEL)
            wan_renderer = self._renderer_entry(
                conn,
                model_key=WAN_MODEL,
                display_name="Wan2.2 TI2V-5B local ComfyUI",
                policy=wan_policy,
                resolutions=[{"width": 1280, "height": 704}, {"width": 704, "height": 1280}],
                capabilities={
                    "image_to_video": True,
                    "local_zero_fee": True,
                    "global_public_candidate": True,
                    "base_clip_seconds": [3, 6],
                },
            )
            hunyuan_renderer = self._renderer_entry(
                conn,
                model_key=HUNYUAN_MODEL,
                display_name="HunyuanVideo 1.5 local ComfyUI",
                policy=hunyuan_policy,
                resolutions=[{"width": 1280, "height": 720}],
                capabilities={
                    "image_to_video": True,
                    "local_zero_fee": True,
                    "territory_policy_required": True,
                    "default_execution_blocked": True,
                },
            )
            wan_profile = self._profile(
                conn,
                provider_key=WAN_PROVIDER,
                model_key=WAN_MODEL,
                display_name="Wan2.2 TI2V-5B local renderer",
                renderer_id=wan_renderer["id"],
                policy_id=wan_policy["id"],
                enable_flag="P114_WAN_EXECUTION_ENABLED",
                acknowledgement_flag="P114_WAN_LICENSE_ACKNOWLEDGED",
                workflow_env="P114_WAN_WORKFLOW_PATH",
                default_workflow=ROOT / "deploy/p114-local-video/workflows/wan2.2-ti2v-5b-i2v-api.json",
                model_files_env="P114_WAN_MODEL_FILES_JSON",
                defaults={"width": 1280, "height": 704, "fps": 24, "steps": 20, "cfg": 5, "sampler": "uni_pc", "scheduler": "simple"},
                default_blocked=False,
            )
            hunyuan_profile = self._profile(
                conn,
                provider_key=HUNYUAN_PROVIDER,
                model_key=HUNYUAN_MODEL,
                display_name="HunyuanVideo 1.5 local renderer",
                renderer_id=hunyuan_renderer["id"],
                policy_id=hunyuan_policy["id"],
                enable_flag="P114_HUNYUAN_EXECUTION_ENABLED",
                acknowledgement_flag="P114_HUNYUAN_LICENSE_ACKNOWLEDGED",
                workflow_env="P114_HUNYUAN_WORKFLOW_PATH",
                default_workflow=None,
                model_files_env="P114_HUNYUAN_MODEL_FILES_JSON",
                defaults={"fps": 24, "recommended_steps": [8, 12], "territory_preflight_required": True},
                default_blocked=True,
            )
        return {
            "ok": True,
            "worker_id": self.worker_id,
            "wan_profile": self._summary(wan_profile),
            "hunyuan_profile": self._summary(hunyuan_profile),
            "automatic_generation": False,
            "automatic_model_download": False,
            "automatic_public_publishing": False,
        }

    def _require_operator(self, conn, operator_id: str) -> None:
        if not conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone():
            raise RuntimeError(f"active operator is required before P114 onboarding: {operator_id}")

    def _ensure_worker(self, conn) -> None:
        row = conn.execute(
            """INSERT INTO football_brief.operator_users
               (operator_id,display_name,active,created_by)
               VALUES (%s,'P114 Local Video Worker',true,%s)
               ON CONFLICT (operator_id) DO UPDATE SET display_name=EXCLUDED.display_name,active=true
               RETURNING id""",
            (self.worker_id, self.actor),
        ).fetchone()
        conn.execute("DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s", (row["id"],))
        conn.execute(
            "INSERT INTO football_brief.operator_user_roles (operator_user_id,role,assigned_by) VALUES (%s,'producer',%s)",
            (row["id"], self.actor),
        )
        conn.execute("DELETE FROM football_brief.operator_brand_assignments WHERE operator_user_id=%s", (row["id"],))
        conn.execute(
            """INSERT INTO football_brief.operator_brand_assignments (operator_user_id,brand_id,assigned_by)
               SELECT %s,id,%s FROM football_brief.brands WHERE active=true ON CONFLICT DO NOTHING""",
            (row["id"], self.actor),
        )

    @staticmethod
    def _policy(conn, provider_key: str, model_key: str):
        row = conn.execute(
            """SELECT * FROM football_brief.video_model_use_policies
               WHERE provider_key=%s AND model_key=%s AND status='active'
               ORDER BY version DESC LIMIT 1""",
            (provider_key, model_key),
        ).fetchone()
        if not row:
            raise RuntimeError(f"active P113 model-use policy is missing for {provider_key}/{model_key}")
        return row

    def _renderer_entry(self, conn, *, model_key: str, display_name: str, policy, resolutions, capabilities):
        provider_key = "local-comfyui"
        active = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE provider_key=%s AND model_key=%s AND operation='image_to_video' AND status='active'
               ORDER BY version DESC LIMIT 1""",
            (provider_key, model_key),
        ).fetchone()
        if active:
            return active
        latest = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE provider_key=%s AND model_key=%s AND operation='image_to_video'
               ORDER BY version DESC LIMIT 1""",
            (provider_key, model_key),
        ).fetchone()
        version = int(latest["version"]) + 1 if latest else 1
        return conn.execute(
            """INSERT INTO football_brief.renderer_catalogue_entries
               (provider_key,provider_display_name,model_key,model_display_name,operation,version,
                parent_entry_id,adapter_kind,status,health_status,supported_formats,min_duration_seconds,
                max_duration_seconds,duration_step_seconds,supported_resolutions,capabilities,
                expected_latency_seconds,pricing,pricing_currency,quality_rating,commercial_use_allowed,
                usage_terms_url,usage_evidence_digest,usage_evidence_recorded_at,data_handling,notes,
                created_by,activated_by,activated_at)
               VALUES (%s,'Local ComfyUI',%s,%s,'image_to_video',%s,%s,'http_api','active','unknown',
                       ARRAY['mp4'],3,6,1,%s::jsonb,%s::jsonb,'{}'::jsonb,
                       '{"per_second":0,"per_request":0}'::jsonb,'USD',0,%s,%s,%s,%s,
                       '{"local_only":true,"credentials_stored":false}'::jsonb,
                       'P114 local renderer; execution requires an active hash-verified profile.',
                       %s,%s,now()) RETURNING *""",
            (
                provider_key,
                model_key,
                display_name,
                version,
                latest["id"] if latest else None,
                _json(resolutions),
                _json(capabilities),
                bool(policy["commercial_use_allowed"]),
                policy["terms_url"],
                policy["evidence_digest"],
                policy["evidence_recorded_at"],
                self.actor,
                self.actor,
            ),
        ).fetchone()

    def _profile(
        self,
        conn,
        *,
        provider_key: str,
        model_key: str,
        display_name: str,
        renderer_id,
        policy_id,
        enable_flag: str,
        acknowledgement_flag: str,
        workflow_env: str,
        default_workflow: Path | None,
        model_files_env: str,
        defaults: dict[str, Any],
        default_blocked: bool,
    ):
        enabled = _true(enable_flag)
        acknowledged = _true(acknowledgement_flag)
        configured_path = os.getenv(workflow_env, "").strip()
        workflow_path = Path(configured_path) if configured_path else default_workflow
        if workflow_path is not None and not workflow_path.is_absolute():
            workflow_path = (ROOT / workflow_path).resolve()
        workflow_digest = _sha256(workflow_path) if workflow_path is not None and workflow_path.is_file() else None
        files = _model_files(model_files_env)

        status = "draft"
        blocked_reason = None
        if default_blocked and not enabled:
            status = "blocked"
            blocked_reason = "Hunyuan execution is disabled until a reviewed API workflow and territory-cleared policy are configured."
        elif enabled:
            if not acknowledged:
                raise RuntimeError(f"{acknowledgement_flag}=true is required before activating {provider_key}/{model_key}")
            if workflow_digest is None:
                raise RuntimeError(f"a readable API workflow is required in {workflow_env}")
            if not files:
                raise RuntimeError(f"hash-verified model files are required in {model_files_env}")
            status = "active"

        desired = {
            "status": status,
            "renderer_catalogue_entry_id": renderer_id,
            "model_policy_id": policy_id,
            "workflow_path": str(workflow_path) if workflow_path is not None else None,
            "workflow_sha256": workflow_digest,
            "model_files": files,
            "default_settings": defaults,
            "blocked_reason": blocked_reason,
        }
        latest = conn.execute(
            """SELECT * FROM football_brief.local_video_renderer_profiles
               WHERE provider_key=%s AND model_key=%s ORDER BY version DESC LIMIT 1""",
            (provider_key, model_key),
        ).fetchone()
        if latest and all(
            (
                latest[key] == value
                if key not in {"model_files", "default_settings"}
                else dict(latest[key]) == value if isinstance(value, dict) else list(latest[key]) == value
            )
            for key, value in desired.items()
        ):
            return latest
        if latest and latest["status"] == "draft":
            return conn.execute(
                """UPDATE football_brief.local_video_renderer_profiles SET
                       display_name=%s,status=%s,renderer_catalogue_entry_id=%s,model_policy_id=%s,
                       workflow_path=%s,workflow_sha256=%s,model_files=%s::jsonb,default_settings=%s::jsonb,
                       activation_evidence=%s::jsonb,blocked_reason=%s,activated_by=%s,activated_at=%s
                   WHERE id=%s RETURNING *""",
                (
                    display_name,
                    status,
                    renderer_id,
                    policy_id,
                    desired["workflow_path"],
                    workflow_digest,
                    _json(files),
                    _json(defaults),
                    _json({"license_acknowledged": acknowledged, "activated_by_onboarding": status == "active"}),
                    blocked_reason,
                    self.actor if status == "active" else None,
                    datetime.now(timezone.utc) if status == "active" else None,
                    latest["id"],
                ),
            ).fetchone()
        if latest and latest["status"] == "active":
            conn.execute(
                "UPDATE football_brief.local_video_renderer_profiles SET status='retired',retired_by=%s,retired_at=now() WHERE id=%s",
                (self.actor, latest["id"]),
            )
        version = int(latest["version"]) + 1 if latest else 1
        return conn.execute(
            """INSERT INTO football_brief.local_video_renderer_profiles
               (provider_key,model_key,display_name,version,parent_profile_id,status,
                renderer_catalogue_entry_id,model_policy_id,workflow_path,workflow_sha256,
                model_files,default_settings,activation_evidence,blocked_reason,created_by,
                activated_by,activated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
               RETURNING *""",
            (
                provider_key,
                model_key,
                display_name,
                version,
                latest["id"] if latest else None,
                status,
                renderer_id,
                policy_id,
                desired["workflow_path"],
                workflow_digest,
                _json(files),
                _json(defaults),
                _json({"license_acknowledged": acknowledged, "activated_by_onboarding": status == "active"}),
                blocked_reason,
                self.actor,
                self.actor if status == "active" else None,
                datetime.now(timezone.utc) if status == "active" else None,
            ),
        ).fetchone()

    @staticmethod
    def _summary(row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "provider_key": row["provider_key"],
            "model_key": row["model_key"],
            "version": int(row["version"]),
            "status": row["status"],
            "workflow_sha256": row["workflow_sha256"],
            "model_file_count": len(row["model_files"] or []),
            "blocked_reason": row["blocked_reason"],
        }


def main() -> int:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        result = P114RendererOnboarding(database).run()
    finally:
        database.close()
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
