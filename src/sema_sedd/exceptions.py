"""Typed error categories for future interface processing increments."""


class SeddError(Exception):
    """Base class for expected application errors."""


class InputError(SeddError):
    """An input cannot be read or interpreted."""


class XmlSecurityError(InputError):
    """XML violates the secure loader policy."""


class UnsupportedRevisionError(InputError):
    """No adapter supports the detected document revision."""


class SemanticError(SeddError):
    """A semantic operation cannot be completed."""


class ReportError(SeddError):
    """A report cannot be generated or written."""
