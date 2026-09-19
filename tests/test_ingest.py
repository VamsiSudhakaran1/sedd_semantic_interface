"""Security and source-metadata behavior of the generic XML loader."""

import socket
from pathlib import Path

import pytest

from sema_sedd.exceptions import (
    InputError,
    InputTooLargeError,
    InvalidXmlError,
    UnsafeXmlError,
    UnsupportedSeddVersionError,
)
from sema_sedd.parser import SourceLocation, load_sedd

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = '<s:DataDictionary xmlns:s="urn:semi-org:xsd.SEDD"'
HINT = (
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd"'
)


def write_xml(tmp_path: Path, data: bytes, name: str = "input.xml") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_real_synthetic_fixture_loads_without_canonical_entities() -> None:
    path = FIXTURES / "relationships/e172-complete.xml"
    document = load_sedd(path)
    assert document.source == path.resolve()
    assert document.byte_count == path.stat().st_size
    assert document.namespace == "urn:semi-org:xsd.SEDD"
    assert document.root.tag == "{urn:semi-org:xsd.SEDD}DataDictionary"
    assert document.root.children[0].tag == "SEDDHeader"
    assert document.root.location == SourceLocation(2, 1)
    assert document.root.children[0].location.line > 2
    assert document.revision_hint is None
    assert [d.code for d in document.diagnostics] == ["MISSING_SCHEMA_HINT"]
    assert not hasattr(document, "entities")


def test_original_tracksys_sample_loads_without_fetching_schema() -> None:
    path = Path("work/references/SEDD_TrackSys_Model404_0225.xml")
    if not path.is_file():
        pytest.skip("Original reference file is intentionally not versioned")
    document = load_sedd(path)
    assert document.revision_hint == "E172-0225"
    assert document.diagnostics == ()
    assert len(document.root.children) == 15
    assert document.root.children[0].location.line == 18


def test_utf8_namespace_schema_hint_and_mixed_content(tmp_path: Path) -> None:
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'{ROOT}{HINT}><SEDDHeader name="Café">a<Part/>β</SEDDHeader></s:DataDictionary>'
    ).encode()
    document = load_sedd(write_xml(tmp_path, payload))
    assert document.revision_hint == "E172-0225"
    assert document.schema_location == ("urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd")
    child = document.root.children[0]
    assert child.attribute("name") == "Café"
    assert child.content[0] == "a"
    assert child.children[0].tag == "Part"
    assert child.content[2] == "β"
    assert child.location == SourceLocation(
        2, payload.decode().splitlines()[1].index("<SEDDHeader") + 1
    )


@pytest.mark.parametrize("data", [b"", b" ", b"<DataDictionary>", b"<a/><b/>", b"<x>\xff</x>"])
def test_empty_or_malformed_xml(tmp_path: Path, data: bytes) -> None:
    with pytest.raises(InvalidXmlError, match="XML"):
        load_sedd(write_xml(tmp_path, data))


@pytest.mark.parametrize(
    "name", ["truncated.xml", "duplicate-attribute.xml", "undeclared-prefix.xml"]
)
def test_existing_malformed_fixtures(name: str) -> None:
    with pytest.raises(InvalidXmlError):
        load_sedd(FIXTURES / "malformed" / name)


@pytest.mark.parametrize(
    "name", ["external-entity.xml", "external-dtd.xml", "entity-expansion.xml"]
)
def test_dtd_and_entity_fixtures_are_rejected(name: str) -> None:
    with pytest.raises(UnsafeXmlError, match="DOCTYPE"):
        load_sedd(FIXTURES / "malformed" / name)


def test_external_entity_cannot_read_a_local_file(tmp_path: Path) -> None:
    secret = tmp_path / "private.txt"
    secret.write_text("DO_NOT_EXPOSE", encoding="utf-8")
    payload = (
        '<!DOCTYPE s:DataDictionary [<!ENTITY leak SYSTEM "'
        + secret.as_uri()
        + '">]>'
        + ROOT
        + ">&leak;</s:DataDictionary>"
    ).encode()
    with pytest.raises(UnsafeXmlError) as error:
        load_sedd(write_xml(tmp_path, payload))
    assert "DO_NOT_EXPOSE" not in str(error.value)
    assert secret.read_text(encoding="utf-8") == "DO_NOT_EXPOSE"


def test_schema_location_is_text_only_and_cannot_access_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    payload = (
        ROOT
        + ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        + ' xsi:schemaLocation="urn:semi-org:xsd.SEDD https://example.invalid/E172-0225-SEDD-Schema.xsd"'
        + "/>"
    ).encode()
    document = load_sedd(write_xml(tmp_path, payload))
    assert document.revision_hint == "E172-0225"
    assert document.diagnostics == ()


def test_deep_nesting_is_rejected_during_parse(tmp_path: Path) -> None:
    payload = (ROOT + ">" + "<n>" * 65 + "</n>" * 65 + "</s:DataDictionary>").encode()
    with pytest.raises(UnsafeXmlError, match="nesting limit"):
        load_sedd(write_xml(tmp_path, payload))


def test_large_file_is_rejected_before_parse(tmp_path: Path) -> None:
    path = write_xml(tmp_path, b"x" * 1025)
    with pytest.raises(InputTooLargeError):
        load_sedd(path, max_bytes=1024)


def test_element_and_attribute_limits(tmp_path: Path) -> None:
    elements = write_xml(tmp_path, (ROOT + "><a/><a/></s:DataDictionary>").encode())
    with pytest.raises(UnsafeXmlError, match="element limit"):
        load_sedd(elements, max_elements=2)
    attrs = write_xml(tmp_path, (ROOT + ' a="1" b="2"/>').encode())
    with pytest.raises(UnsafeXmlError, match="attribute limit"):
        load_sedd(attrs, max_attributes=1)


@pytest.mark.parametrize(
    "xml",
    [
        '<DataDictionary xmlns="urn:incorrect"/>',
        "<DataDictionary/>",
        '<s:Other xmlns:s="urn:semi-org:xsd.SEDD"/>',
    ],
)
def test_unexpected_namespace_or_root(tmp_path: Path, xml: str) -> None:
    with pytest.raises(UnsupportedSeddVersionError):
        load_sedd(write_xml(tmp_path, xml.encode()))


def test_unrecognized_schema_location_is_diagnostic_not_a_version(tmp_path: Path) -> None:
    xml = ROOT + HINT.replace("E172-0225", "E172-9999") + "/>"
    document = load_sedd(write_xml(tmp_path, xml.encode()))
    assert document.revision_hint is None
    assert [d.code for d in document.diagnostics] == ["UNRECOGNIZED_SCHEMA_HINT"]


def test_input_error_and_limit_configuration(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="Unable to read"):
        load_sedd(tmp_path / "missing.xml")
    with pytest.raises(ValueError, match="positive"):
        load_sedd(tmp_path / "missing.xml", max_depth=0)
