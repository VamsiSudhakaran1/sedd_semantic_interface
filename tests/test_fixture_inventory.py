"""Check fixture bookkeeping and XML mechanics, without implementing an adapter."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST: dict[str, Any] = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
RECORDS: list[dict[str, Any]] = MANIFEST["fixtures"]


def test_every_contract_concept_has_evidence_or_explicit_pending_status() -> None:
    contract = (ROOT / "MASTER_PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
    domain = contract.split("## CANONICAL DOMAIN", 1)[1].split("## RELATIONSHIPS", 1)[0]
    expected = {
        line.removeprefix("* ").rstrip(";.")
        for line in domain.splitlines()
        if line.startswith("* ")
    }
    rows = MANIFEST["coverage"]
    assert len(rows) == len(expected)
    assert {row["concept"] for row in rows} == expected
    for row in rows:
        assert row["status"] in {"PENDING", "OBSERVED"}
        if row["status"] == "PENDING":
            assert row["reason"]
        else:
            assert row["evidence"], "Observed coverage needs source evidence"
        assert row["fixtures"]
        for name in row["fixtures"]:
            assert (FIXTURES / name).is_file()


def test_inventory_is_complete_and_paths_stay_within_fixtures() -> None:
    declared = [record["path"] for record in RECORDS]
    assert len(declared) == len(set(declared))
    actual = {
        str(path.relative_to(FIXTURES).as_posix())
        for path in FIXTURES.rglob("*")
        if path.suffix in {".xml", ".json"} and path.name != "manifest.json"
    }
    assert set(declared) == actual
    assert {Path(name).parts[0] for name in declared} == {
        "minimal",
        "relationships",
        "malformed",
        "changes",
    }
    for name in declared:
        assert (FIXTURES / name).resolve().is_relative_to(FIXTURES.resolve())


def test_unavailable_references_cannot_claim_verified_e172_fixtures() -> None:
    if MANIFEST["reference_analysis_status"] == "BLOCKED_REFERENCE_ACCESS":
        assert all(row["status"] == "PENDING" for row in MANIFEST["coverage"])
        assert all(record["e172_validity"] == "NOT_ESTABLISHED" for record in RECORDS)
        assert all(source["sha256"] is None for source in MANIFEST["sources"].values())


@pytest.mark.parametrize("record", RECORDS, ids=[record["path"] for record in RECORDS])
def test_fixture_classification(record: dict[str, Any]) -> None:
    data = (FIXTURES / record["path"]).read_bytes()
    if record["kind"] == "scenario-plan":
        plan = json.loads(data)
        assert plan["status"] == "PENDING"
        assert plan["classification"] == "ASSUMPTION"
        assert plan["e172_validity"] == "NOT_ESTABLISHED"
        assert plan["pending"]
        return
    assert (b"<!DOCTYPE" in data) == record["contains_doctype"]
    if record["contains_doctype"]:
        # Do not parse security payloads with a general-purpose XML parser.
        assert record["future_processing"] == "REJECT_DTD"
        return
    if record["xml_syntax"] == "INVALID":
        with pytest.raises(ET.ParseError):
            ET.fromstring(data)
    else:
        ET.fromstring(data)


def test_noise_pair_changes_serialization_but_retains_probe_values() -> None:
    before = (FIXTURES / "changes/noise-before.xml").read_bytes()
    after = (FIXTURES / "changes/noise-after.xml").read_bytes()
    assert before != after
    left, right = ET.fromstring(before), ET.fromstring(after)
    assert left.tag == right.tag == "{urn:sema-sedd:fixture-only:1}probe"
    assert left.attrib == right.attrib
    assert left[0].tag == right[0].tag
    assert left[0].text == right[0].text


def test_significant_text_pair_has_actual_content_difference() -> None:
    left = ET.parse(FIXTURES / "changes/text-before.xml").getroot()
    right = ET.parse(FIXTURES / "changes/text-after.xml").getroot()
    assert left[0].text == "alpha beta"
    assert right[0].text == "alphabeta"


def test_report_injection_probe_is_text_not_an_xml_script_element() -> None:
    root = ET.parse(FIXTURES / "malformed/report-markup.xml").getroot()
    assert root[0].text == '<script>alert("synthetic")</script>'
    assert len(root[0]) == 0
