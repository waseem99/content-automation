from enum import StrEnum


class AssetSourceType(StrEnum):
    OWNED = "owned"
    COMMISSIONED = "commissioned"
    LICENSED = "licensed"
    STOCK = "stock"
    CREATIVE_COMMONS = "creative_commons"
    PUBLIC_DOMAIN = "public_domain"
    AI_GENERATED = "ai_generated"
    CLIENT_SUPPLIED = "client_supplied"
    UNKNOWN = "unknown"


class AssetLifecycleStatus(StrEnum):
    CANDIDATE = "candidate"
    INTERNAL_ONLY = "internal_only"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
