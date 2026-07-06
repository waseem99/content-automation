class LineageError(RuntimeError):
    pass


class DerivativeRegistrationError(LineageError):
    pass


class ProviderCallError(LineageError):
    pass


class LineageIntegrityError(LineageError):
    pass
