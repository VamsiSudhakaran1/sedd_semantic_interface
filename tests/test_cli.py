"""Check the installed public command-line contract."""

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from sema_sedd.cli import main
from sema_sedd.exceptions import (
    InputError,
    ReportError,
    SeddError,
    SemanticError,
    UnsupportedRevisionError,
    XmlSecurityError,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("args", [[], ["--help"], ["--version"]])
def test_module_cli(args: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sema_sedd", *args], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert result.stderr == ""
    if args == ["--version"]:
        assert result.stdout.strip() == f"sedd {version('sema-sedd')}"
    else:
        assert "--help" in result.stdout
        assert "--version" in result.stdout
        assert "inspect" in result.stdout
        assert "explore" in result.stdout


@pytest.mark.parametrize("arg", ["report", "--bogus", "--ver"])
def test_unsupported_arguments(arg: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main([arg])
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_no_argument_entry_point(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: sedd" in capsys.readouterr().out


def hinted_fixture(tmp_path: Path, name: str) -> Path:
    source = FIXTURES / "relationships" / name
    text = source.read_text(encoding="utf-8")
    root = '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD">'
    hinted = (
        '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">'
    )
    assert root in text
    path = tmp_path / name
    path.write_text(text.replace(root, hinted, 1), encoding="utf-8")
    return path


def test_inspect_text_displays_required_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert main(["inspect", str(path)]) == 0
    output = capsys.readouterr().out
    assert "SEDD revision: E172-0225" in output
    assert "model: Lantern17" in output
    assert "collection_event: 2" in output
    assert "alarm: 1" in output
    assert "Unresolved references: 1" in output
    assert "UNRESOLVED/not_found" in output
    assert "Unsupported sections: 1" in output
    assert "RecipeVariableParameters" in output
    assert "Diagnostics: 4" in output
    assert "REVISION_HINT_ONLY" in output
    assert "UNSUPPORTED_EXTENSION" in output
    assert "UNRESOLVED_REFERENCE" in output
    assert "REFERENCE_RESOLUTION_PENDING" not in output


def test_inspect_json_is_deterministic_and_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    args = ["inspect", str(path), "--json"]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    assert first == first.strip() + "\n"

    data = json.loads(first)
    assert data["inspection_schema_version"] == "2.0"
    assert data["sedd_revision"] == "E172-0225"
    assert data["equipment"]["model"] == "Lantern17"
    assert data["entity_counts"]["collection_event"] == 2
    assert len(data["unresolved_references"]) == 1
    assert data["unresolved_references"][0]["reason"] == "not_found"
    assert data["unsupported_sections"][0]["name"] == "RecipeVariableParameters"
    assert [item["code"] for item in data["diagnostics"]] == [
        "MISSING_OPTIONAL_METADATA",
        "REVISION_HINT_ONLY",
        "UNRESOLVED_REFERENCE",
        "UNSUPPORTED_EXTENSION",
    ]
    assert data["selection"] is None


def test_entity_filters_are_exact_conjunctive_and_show_immediate_relationships(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert main(["inspect", str(path), "--json", "--type", "alarm", "--id", "1001"]) == 0
    data = json.loads(capsys.readouterr().out)
    selection = data["selection"]
    assert selection["filters"] == {"id": "1001", "type": "alarm", "wkn": None}
    assert selection["count"] == 1
    selected = selection["entities"][0]
    assert selected["entity"]["canonical_type"] == "alarm"
    assert selected["entity"]["implementation_id"] == "1001"
    assert {item["role"] for item in selected["immediate_relationships"]} == {
        "set_event",
        "clear_event",
    }
    assert {item["state"] for item in selected["immediate_relationships"]} == {"resolved"}


def test_wkn_filter_and_no_match_are_reported_without_guessing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-complete.xml")
    wkn = "urn:sema-sedd:fictional:702"
    assert main(["inspect", str(path), "--json", "--type", "status_variable", "--wkn", wkn]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["selection"]["count"] == 1
    assert data["selection"]["entities"][0]["entity"]["wkn"]["value"] == wkn

    assert main(["inspect", str(path), "--json", "--id", "0702"]) == 0
    assert json.loads(capsys.readouterr().out)["selection"]["count"] == 0


def test_entity_detail_includes_incoming_and_containment_relationships(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    events = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert (
        main(["inspect", str(events), "--json", "--type", "collection_event", "--id", "801"]) == 0
    )
    event = json.loads(capsys.readouterr().out)["selection"]["entities"][0]
    incoming_roles = {
        item["role"] for item in event["immediate_relationships"] if item["direction"] == "incoming"
    }
    assert incoming_roles == {"set_event", "event"}

    complete = hinted_fixture(tmp_path, "e172-complete.xml")
    assert main(["inspect", str(complete), "--json", "--type", "remote_command"]) == 0
    command = json.loads(capsys.readouterr().out)["selection"]["entities"][0]
    assert any(
        item.get("kind") == "containment" and item["direction"] == "outgoing"
        for item in command["immediate_relationships"]
    )


def test_inspect_errors_are_controlled(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as missing:
        main(["inspect", str(tmp_path / "missing.xml")])
    assert missing.value.code == 2
    captured = capsys.readouterr()
    assert "Unable to read XML input" in captured.err
    assert "Traceback" not in captured.err

    path = hinted_fixture(tmp_path, "e172-complete.xml")
    with pytest.raises(SystemExit) as invalid_type:
        main(["inspect", str(path), "--type", "StatusVariable"])
    assert invalid_type.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_explore_text_displays_entity_properties_and_both_directions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert main(["explore", str(path), "event:801"]) == 0
    output = capsys.readouterr().out
    assert "SEDD revision: E172-0225" in output
    assert "Entity (depth 0): collection_event" in output
    assert "Properties:" in output
    assert "Incoming relationships: 2" in output
    assert "Outgoing relationships:" in output
    assert "Entity (depth 1): alarm" in output
    assert "Entity (depth 1): event_report_link" in output


def test_explore_json_is_deterministic_and_depth_bounded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    args = ["explore", str(path), "alarm:1001", "--depth", "2", "--json"]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    assert first == first.strip() + "\n"

    data = json.loads(first)
    assert data["exploration_schema_version"] == "1.0"
    assert data["selector"] == {"kind": "alarm", "value": "1001"}
    assert data["max_depth"] == 2
    assert [(item["entity"]["canonical_type"], item["depth"]) for item in data["entities"]] == [
        ("alarm", 0),
        ("collection_event", 1),
        ("collection_event", 1),
        ("event_report_link", 2),
    ]
    assert max(item["depth"] for item in data["entities"]) == 2


def test_explore_depth_zero_shows_relationships_without_traversal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert main(["explore", str(path), "alarm:1001", "--depth", "0", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["entities"]) == 1
    root = data["entities"][0]
    assert root["depth"] == 0
    assert {item["role"] for item in root["outgoing_relationships"]} == {
        "clear_event",
        "set_event",
    }


def test_explore_status_variable_and_wkn_select_the_same_entity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-complete.xml")
    selectors = ["status-variable:702", "wkn:urn:sema-sedd:fictional:702"]
    root_keys = []
    for selector in selectors:
        assert main(["explore", str(path), selector, "--depth", "0", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        root_keys.append(data["root_key"])
        assert data["entities"][0]["entity"]["canonical_type"] == "status_variable"
    assert root_keys[0] == root_keys[1]


def test_explore_shows_unresolved_relationship_but_does_not_traverse_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    assert main(["explore", str(path), "event:801", "--depth", "8", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    report = next(
        item for item in data["entities"] if item["entity"]["canonical_type"] == "default_report"
    )
    unresolved = report["outgoing_relationships"]
    assert len(unresolved) == 1
    assert unresolved[0]["state"] == "unresolved"
    assert unresolved[0]["target_key"] is None
    assert unresolved[0]["reason"] == "not_found"
    assert len(data["entities"]) == 5


def test_explore_shows_ambiguous_relationship_but_does_not_traverse_candidates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    text = path.read_text(encoding="utf-8")
    duplicates = (
        "<DataVariables>"
        "<DataVariable><VID>799</VID><DVVALNAME>First</DVVALNAME></DataVariable>"
        "<DataVariable><VID>799</VID><DVVALNAME>Second</DVVALNAME></DataVariable>"
        "</DataVariables>"
    )
    path.write_text(text.replace("<DataVariables/>", duplicates), encoding="utf-8")

    assert main(["explore", str(path), "event:801", "--depth", "8", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    report = next(
        item for item in data["entities"] if item["entity"]["canonical_type"] == "default_report"
    )
    ambiguous = report["outgoing_relationships"][0]
    assert ambiguous["state"] == "ambiguous"
    assert len(ambiguous["candidate_keys"]) == 2
    assert all(item["entity"]["canonical_type"] != "data_variable" for item in data["entities"])


@pytest.mark.parametrize(
    "selector",
    ["event", "command:Start", "event:", ":801", "Event:801", "event:0801"],
)
def test_explore_selector_errors_are_controlled(
    tmp_path: Path, selector: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    with pytest.raises(SystemExit) as error:
        main(["explore", str(path), selector])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_explore_rejects_ambiguous_selector(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("<CEID>802</CEID>", "<CEID>801</CEID>"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as error:
        main(["explore", str(path), "event:801"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "is ambiguous; it matched 2 entities" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("depth", ["-1", "9", "one", "1.5"])
def test_explore_rejects_unbounded_or_invalid_depth(
    tmp_path: Path, depth: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = hinted_fixture(tmp_path, "e172-event-alarm-report.xml")
    with pytest.raises(SystemExit) as error:
        main(["explore", str(path), "event:801", "--depth", depth])
    assert error.value.code == 2
    assert "depth must" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error_type",
    [InputError, XmlSecurityError, UnsupportedRevisionError, SemanticError, ReportError],
)
def test_typed_errors(error_type: type[SeddError]) -> None:
    error = error_type("context")
    assert isinstance(error, SeddError)
    assert str(error) == "context"
