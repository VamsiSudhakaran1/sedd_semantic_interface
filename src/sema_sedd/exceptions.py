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
    """The root QName is not a supported SEDD document root."""


class SemanticError(SeddError):
    """A semantic operation cannot be completed."""


class ReportError(SeddError):
    """A report cannot be generated or written."""
