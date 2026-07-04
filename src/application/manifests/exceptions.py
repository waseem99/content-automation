class ManifestError(RuntimeError):
    pass


class ManifestValidationError(ManifestError):
    pass


class ManifestIntegrityError(ManifestError):
    pass


class ManifestNotPublishable(ManifestError):
    pass


class ManifestRenderError(ManifestError):
    pass
