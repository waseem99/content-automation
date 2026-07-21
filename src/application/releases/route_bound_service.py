from __future__ import annotations

from typing import Any

from src.application.releases.audio_bound_service import AudioBoundFinalReleaseService
from src.application.releases.service import FinalReleaseError


class RouteBoundFinalReleaseService(AudioBoundFinalReleaseService):
    """Canonical release service with exact P94 route-output preflight checks."""

    @staticmethod
    def _require_routing_ready(conn: Any, release: Any) -> None:
        AudioBoundFinalReleaseService._require_routing_ready(conn, release)
        if release["routing_plan_id"] is None:
            return

        mismatches = conn.execute(
            """SELECT sri.id AS routing_item_id,sri.visual_shot_id,sri.route,
                      fri.id AS release_input_id,fri.artifact_version_id,fri.canonical_asset_id,
                      vc.asset_id AS selected_candidate_asset_id,
                      psr.status AS reservation_status,
                      gj.status AS generation_job_status,
                      gj.output_payload->>'shared_artifact_version_id' AS managed_artifact_version_id
               FROM football_brief.final_release_inputs fri
               JOIN football_brief.shot_routing_items sri
                 ON sri.id=(fri.metadata->>'routing_item_id')::uuid
               LEFT JOIN football_brief.visual_candidates vc
                 ON vc.id=sri.selected_candidate_id
               LEFT JOIN football_brief.production_spend_reservations psr
                 ON psr.routing_item_id=sri.id
               LEFT JOIN football_brief.generation_jobs gj
                 ON gj.id=psr.generation_job_id
               WHERE fri.release_id=%s
                 AND fri.role='visual_shot'
                 AND (
                     (
                         sri.route<>'managed_render'
                         AND fri.canonical_asset_id IS DISTINCT FROM vc.asset_id
                     )
                     OR
                     (
                         sri.route='managed_render'
                         AND (
                             psr.status IS DISTINCT FROM 'reconciled'
                             OR gj.status IS DISTINCT FROM 'succeeded'
                             OR gj.output_payload->>'shared_artifact_version_id'
                                IS DISTINCT FROM fri.artifact_version_id::text
                         )
                     )
                 )
               ORDER BY sri.id""",
            (release["id"],),
        ).fetchall()
        if mismatches:
            raise FinalReleaseError(
                "final_release_route_outputs_mismatch",
                details={"items": [dict(row) for row in mismatches]},
            )
