from src.application.pre_generation.service import (
    PreGenerationError,
    PreGenerationService,
)
from src.application.pre_generation.runtime_patch import install_pre_generation_runtime_patch
from src.application.pre_generation.final_runtime_patch import install_final_pre_generation_runtime_patch
from src.application.pre_generation.campaign_claim_patch import install_campaign_scoped_claim_patch


install_pre_generation_runtime_patch()
install_final_pre_generation_runtime_patch()
install_campaign_scoped_claim_patch()


__all__ = ["PreGenerationError", "PreGenerationService"]
