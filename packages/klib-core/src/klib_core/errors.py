class KlibError(Exception):
    """Base error for user-facing K-LIB failures."""


class LibraryNotFoundError(KlibError):
    """Raised when a library id or path cannot be resolved."""


class ManifestValidationError(KlibError):
    """Raised when a manifest does not satisfy the package specification."""


class ModelProviderError(KlibError):
    """Raised when a model endpoint fails or returns an invalid response."""

