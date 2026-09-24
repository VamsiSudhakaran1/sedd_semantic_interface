"""Install the wheel into a fresh venv and test from outside the source tree."""

import argparse
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=root / "dist")
    args = parser.parse_args()
    wheels = list(args.dist_dir.resolve().glob("*.whl"))
    assert len(wheels) == 1, "Expected exactly one built wheel"
    with tempfile.TemporaryDirectory() as directory:
        env = Path(directory) / "env"
        venv.create(env, with_pip=True)
        scripts = env / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        command = scripts / ("sedd.exe" if os.name == "nt" else "sedd")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-index", str(wheels[0])], check=True
        )
        for executable in ([str(command)], [str(python), "-m", "sema_sedd"]):
            for flag in ("--help", "--version"):
                result = subprocess.run(
                    [*executable, flag], cwd=directory, capture_output=True, text=True, check=True
                )
                assert "sedd" in result.stdout
                assert not result.stderr
        subprocess.run(
            [
                str(python),
                "-c",
                "from importlib.resources import files; "
                "assert files('sema_sedd').joinpath('py.typed').is_file()",
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.parser import load_sedd; "
                "import sys; "
                "assert load_sedd(sys.argv[1]).root.tag == "
                "'{urn:semi-org:xsd.SEDD}DataDictionary'",
                str(root / "tests" / "fixtures" / "minimal" / "e172-empty.xml"),
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.model import EquipmentInterface, StatusVariable, "
                "to_canonical_json; import json; "
                "data = json.loads(to_canonical_json(EquipmentInterface("
                "status_variables=(StatusVariable(key='sv', implementation_id='007'),)))); "
                "assert data['interface']['status_variables'][0]['implementation_id'] == '007'",
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.adapters import load_interface; "
                "from sema_sedd.model import to_canonical_json; import sys; "
                "result = load_interface(sys.argv[1], revision='E172-0225'); "
                "assert result.interface.equipment.model == 'Lantern17'; "
                "assert to_canonical_json(result.interface)",
                str(root / "tests" / "fixtures" / "minimal" / "e172-empty.xml"),
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.adapters import load_interface; "
                "from sema_sedd.graph import ResolutionState, resolve_references; "
                "import sys; "
                "parsed = load_interface(sys.argv[1], revision='E172-0225').interface; "
                "result = resolve_references(parsed); "
                "assert sum(r.state is ResolutionState.RESOLVED "
                "for r in result.relationships) == 4",
                str(root / "tests" / "fixtures" / "relationships" / "e172-event-alarm-report.xml"),
            ],
            cwd=directory,
            check=True,
        )
        source = root / "tests" / "fixtures" / "relationships" / "e172-event-alarm-report.xml"
        inspect_input = Path(directory) / "inspect.xml"
        inspect_input.write_text(
            source.read_text(encoding="utf-8").replace(
                '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD">',
                '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">',
                1,
            ),
            encoding="utf-8",
        )
        inspected = subprocess.run(
            [str(command), "inspect", str(inspect_input), "--json", "--type", "alarm"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        inspection = json.loads(inspected.stdout)
        assert inspection["sedd_revision"] == "E172-0225"
        assert inspection["selection"]["count"] == 1
        assert not inspected.stderr
        explored = subprocess.run(
            [
                str(command),
                "explore",
                str(inspect_input),
                "alarm:1001",
                "--depth",
                "1",
                "--json",
            ],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        exploration = json.loads(explored.stdout)
        assert exploration["sedd_revision"] == "E172-0225"
        assert exploration["selector"] == {"kind": "alarm", "value": "1001"}
        assert [item["depth"] for item in exploration["entities"]] == [0, 1, 1]
        assert not explored.stderr
        compare_input = Path(directory) / "compare-new.xml"
        compare_input.write_text(
            inspect_input.read_text(encoding="utf-8").replace(
                "<ALTX>Synthetic warning</ALTX>",
                "<ALTX>Synthetic warning revised</ALTX>",
                1,
            ),
            encoding="utf-8",
        )
        compared = subprocess.run(
            [
                str(command),
                "compare",
                str(inspect_input),
                str(compare_input),
                "--json",
                "--type",
                "alarm",
                "--only-changed",
            ],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        comparison = json.loads(compared.stdout)
        assert comparison["summary"]["property_changes"] == 1
        assert comparison["property_changes"][0]["change"]["kind"] == "ALARM_CHANGED"
        assert comparison["diagnostics"]
        assert comparison["summary"]["is_complete"] is False
        assert not compared.stderr
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.report import report_json, report_schema; "
                "from sema_sedd.reporting import report_files; "
                "import json, sys; "
                "schema = report_schema(); "
                "assert schema['properties']['report_schema_version']['const'] == '1.0'; "
                "report = report_files(sys.argv[1], sys.argv[2]); "
                "assert set(schema['required']) == set(report); "
                "assert any(row['change_id'] == 'AL_ALARM_CHANGED' "
                "for row in report['changes']); "
                "assert json.loads(report_json(report)) == report",
                str(inspect_input),
                str(compare_input),
            ],
            cwd=directory,
            check=True,
        )
        html_output = Path(directory) / "comparison.html"
        generated = subprocess.run(
            [
                str(command),
                "report",
                str(inspect_input),
                str(compare_input),
                "--html",
                str(html_output),
            ],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        html = html_output.read_text(encoding="utf-8")
        assert "AL_ALARM_CHANGED" in html
        assert "Search changed entities" in html
        assert "connect-src 'none'" in html
        assert str(html_output) in generated.stdout
        assert not generated.stderr
        interface_output = Path(directory) / "interface.html"
        explored_html = subprocess.run(
            [str(command), "report", str(inspect_input), "--html", str(interface_output)],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        interface_html = interface_output.read_text(encoding="utf-8")
        assert "SEDD interface explorer" in interface_html
        assert "Incoming relationships" in interface_html
        assert "Outgoing relationships" in interface_html
        assert "Standards/WKN" in interface_html
        assert "connect-src 'none'" in interface_html
        assert str(interface_output) in explored_html.stdout
        assert not explored_html.stderr
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.compare import match_interfaces, IdentityChangeKind, "
                "compare_interfaces, ChangeKind, to_change_set_json; "
                "from dataclasses import replace; import json; "
                "from sema_sedd.model import EquipmentInterface, StatusVariable, "
                "WellKnownName, WknAuthority, SourceProvenance; "
                "wkn = WellKnownName(value='synthetic.value', authority='fictional-registry', "
                "scope='fixture', authority_status=WknAuthority.VERIFIED, "
                "provenance=(SourceProvenance(source_document='synthetic.json'),)); "
                "old = EquipmentInterface(status_variables=("
                "StatusVariable(key='old', implementation_id='44', wkn=wkn),)); "
                "new = EquipmentInterface(status_variables=("
                "StatusVariable(key='new', implementation_id='8044', wkn=wkn),)); "
                "result = match_interfaces(old, new); "
                "assert len(result.matches) == 1; "
                "assert result.matches[0].changes[0].kind is "
                "IdentityChangeKind.IMPLEMENTATION_ID_CHANGED; "
                "assert not result.unmatched_old and not result.unmatched_new; "
                "changes = compare_interfaces(old, new); "
                "assert changes.is_complete and changes.has_interface_changes; "
                "assert changes.entity_changes[0].old_context.subject_key == 'old'; "
                "assert changes.entity_changes[0].new_context.subject_key == 'new'; "
                "assert len(changes.entity_changes) == 1; "
                "assert ChangeKind.IMPLEMENTATION_ID_CHANGED in changes.entity_changes[0].kinds; "
                "documented = replace(old, status_variables=("
                "replace(old.status_variables[0], description='Updated documentation'),)); "
                "docs = compare_interfaces(old, documented); "
                "assert docs.has_documentation_changes and not docs.has_interface_changes; "
                "assert json.loads(to_change_set_json(docs))['change_schema_version'] == '1.0'; "
                "from sema_sedd.graph import build_dependency_index, resolve_references, "
                "DependencyKind; "
                "from sema_sedd.model import DefaultReport, EntityReference, CanonicalType; "
                "linked = replace(old, default_reports=(DefaultReport(key='report', "
                "implementation_id='1', variables=(EntityReference("
                "target_types=(CanonicalType.STATUS_VARIABLE,), implementation_id='44'),)),)); "
                "context = build_dependency_index(resolve_references(linked)).context_for('old'); "
                "assert context.statements == ('Referenced by 1 default report.',); "
                "assert context.dependencies[0].kind is DependencyKind.REFERENCED_BY",
            ],
            cwd=directory,
            check=True,
        )
    print(
        "Isolated installation, inspect/explore CLI, loader, model, adapter, "
        "graph, cross-version matching, semantic comparison, dependency context, "
        "compare CLI, JSON report contract, HTML comparison, and single-file "
        "explorer checks passed."
    )


if __name__ == "__main__":
    main()
