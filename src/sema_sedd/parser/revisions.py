"""Revision hints for the supported SEDD XML family.

These strings identify a schema hint, not proof of revision conformance.
"""

from urllib.parse import urlsplit

SEDD_NAMESPACE = "urn:semi-org:xsd.SEDD"
SEDD_ROOT = f"{{{SEDD_NAMESPACE}}}DataDictionary"
XSI_SCHEMA_LOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"

_SCHEMA_FILENAMES: dict[str, str] = {
    "E172-0225-SEDD-Schema.xsd": "E172-0225",
}


def revision_from_schema_location(value: str | None) -> tuple[str | None, str | None]:
    """Inspect the untrusted schemaLocation text without opening any URL."""
    if value is None:
        return None, "MISSING_SCHEMA_HINT"
    parts = value.split()
    if not parts or len(parts) % 2:
        return None, "MALFORMED_SCHEMA_HINT"
    locations = [
        parts[index + 1] for index in range(0, len(parts), 2) if parts[index] == SEDD_NAMESPACE
    ]
    if len(locations) != 1:
        return None, "AMBIGUOUS_SCHEMA_HINT" if locations else "MISSING_SCHEMA_HINT"
    filename = urlsplit(locations[0]).path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    revision = _SCHEMA_FILENAMES.get(filename)
    return (revision, None) if revision else (None, "UNRECOGNIZED_SCHEMA_HINT")
