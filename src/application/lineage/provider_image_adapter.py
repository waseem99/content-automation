from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.application.assets.resolver import AssetResolver
from src.application.lineage.exceptions import DerivativeRegistrationError
from src.application.lineage.models import DerivativeRegistrationRequest, DerivativeRegistrationResult
from src.application.lineage.service import AssetLineageService


ImageEditCallback = Callable[[Path, Path], None]


class LineageAwareImageAdapter:
    def __init__(self, *, resolver: AssetResolver, lineage: AssetLineageService) -> None:
        self.resolver = resolver
        self.lineage = lineage

    def edit_registered_parent(
        self,
        request: DerivativeRegistrationRequest,
        callback: ImageEditCallback,
    ) -> DerivativeRegistrationResult:
        parent = self.resolver.resolve(request.parent_asset_id, verify_hash=True)
        before_mtime = parent.path.stat().st_mtime_ns
        before_size = parent.path.stat().st_size
        if request.output_path.resolve() == parent.path.resolve():
            raise DerivativeRegistrationError("Derivative output path must not overwrite source asset")

        callback(parent.path, request.output_path)

        if not request.output_path.is_file():
            raise DerivativeRegistrationError("Provider image edit did not create an output file")
        after = parent.path.stat()
        if after.st_mtime_ns != before_mtime or after.st_size != before_size:
            raise DerivativeRegistrationError("Provider image edit modified the source asset")
        return self.lineage.register_derivative(request)
