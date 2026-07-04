from __future__ import annotations

from uuid import UUID

from src.application.manifests.exceptions import ManifestValidationError
from src.application.manifests.models import RenderManifestBuildRequest
from src.domain.render_status import ManifestAssetRole


def validate_asset_roles(request: RenderManifestBuildRequest) -> None:
    keys = [(item.role.value, item.sequence_number) for item in request.assets]
    if len(keys) != len(set(keys)):
        raise ManifestValidationError("Asset role and sequence combinations must be unique")

    actual_ids = {item.asset_id for item in request.assets if item.asset_id is not None}
    role_by_asset: dict[UUID, set[ManifestAssetRole]] = {}
    for item in request.assets:
        if item.asset_id is not None:
            role_by_asset.setdefault(item.asset_id, set()).add(item.role)

    if request.voice_asset_id is not None:
        if request.voice_asset_id not in actual_ids:
            raise ManifestValidationError("Voice asset must be included in manifest assets")
        if ManifestAssetRole.VOICE not in role_by_asset[request.voice_asset_id]:
            raise ManifestValidationError("Voice asset must use the voice role")

    if request.music_asset_id is not None:
        if request.music_asset_id not in actual_ids:
            raise ManifestValidationError("Music asset must be included in manifest assets")
        if ManifestAssetRole.MUSIC not in role_by_asset[request.music_asset_id]:
            raise ManifestValidationError("Music asset must use the music role")
