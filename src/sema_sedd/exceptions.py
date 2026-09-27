"""Typed error categories for future interface processing increments."""


class SeddError(Exception):
    """Base class for expected application errors."""


class InputError(SeddError):
    """An input cannot be read or interpreted."""


class XmlSecurityError(InputError):
    """XML violates the secure loader policy."""


class UnsafeXmlError(XmlSecurityError):
    """The input uses forbidden XML features or exceeds structural limits."""


class InvalidXmlError(InputError):
    """The input is empty, incorrectly encoded, or not well-formed XML."""


class InputTooLargeError(InputError):
    """The input exceeds the configured byte limit."""


class UnsupportedRevisionError(InputError):
    """No adapter supports the detected document revision."""


class UnsupportedSeddVersionError(UnsupportedRevisionError):
    """No safe semantic mapping is available; retain a detected label if present."""

    status = "unsupported"

    def __init__(
        self,
        message: str,
        *,
        detected_revision: str | None = None,
        diagnostic_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.detected_revision = detected_revision
        self.diagnostic_code = diagnostic_code


class SemanticError(SeddError):
    """A semantic operation cannot be completed."""


class ReportError(SeddError):
    """A report cannot be generated or written."""


class ModelValidationError(SemanticError):
    """A canonical object violates a model invariant or field type."""


class EntitySelectionError(SemanticError):
    """An explicit entity selector is invalid, missing, or ambiguous."""


class AdapterRegistrationError(SeddError):
    """An adapter registry or adapter result violates its contract."""


class AmbiguousSeddVersionError(UnsupportedSeddVersionError):
    """Multiple registered adapters claim the same document."""

    status = "ambiguous"
