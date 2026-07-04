from enum import StrEnum


class AssetType(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    FONT = "font"
    DOCUMENT = "document"
    LICENSE_EVIDENCE = "license_evidence"
    GENERATED_GRAPHIC = "generated_graphic"
    VOICE = "voice"
