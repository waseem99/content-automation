class AssetRegistryError(RuntimeError):
    """Base exception for canonical asset registration and resolution."""


class AssetNotFound(AssetRegistryError):
    pass


class AssetStorageMissing(AssetRegistryError):
    pass


class AssetHashMismatch(AssetRegistryError):
    pass


class UnsupportedStorageUri(AssetRegistryError):
    pass


class AssetUnavailable(AssetRegistryError):
    pass


class InvalidParentAsset(AssetRegistryError):
    pass


class FileChangedDuringHashing(AssetRegistryError):
    pass


class InvalidAssetPath(AssetRegistryError):
    pass
