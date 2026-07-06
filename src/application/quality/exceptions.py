class QualityGateError(RuntimeError):
    pass


class MediaInspectionError(QualityGateError):
    pass


class PublicationPackageBlocked(QualityGateError):
    pass
