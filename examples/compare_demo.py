"""Demonstrate caller-supplied fictional WKN evidence and canonical datatype fields.

Only the bundled original fixtures and fictional registry are used. This is a
library tutorial, not an authority-verification feature of the production CLI.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.model import EquipmentInterface, SourceProvenance, WknAuthority
from sema_sedd.report import ReportSource, report_from_changes, report_json

EXAMPLES = Path(__file__).resolve().parent


def prepare_demo_interface(interface: EquipmentInterface) -> EquipmentInterface:
    """Enrich just the tutorial pressure variable using explicit fictional evidence."""
    registry = json.loads((EXAMPLES / "fictional-wkn.json").read_text(encoding="utf-8"))
    variables = []
    for variable in interface.status_variables:
        if variable.wkn is None or variable.wkn.value != registry["value"]:
            variables.append(variable)
            continue
        if (
            interface.equipment.model != "ExampleMachine"
            or variable.name != registry["name"]
            or variable.implementation_id not in registry["implementation_ids"]
        ):
            raise ValueError("Fictional registry does not describe this tutorial entity")
        definitions = [
            fmt
            for fmt in interface.variable_formats
            if variable.format is not None and fmt.name == variable.format.name
        ]
        if len(definitions) != 1 or definitions[0].structure is None:
            raise ValueError("Tutorial pressure format must have one definition")
        shapes = definitions[0].structure
        if len(shapes) != 1 or len(shapes[0].children) != 1:
            raise ValueError("Tutorial format must have one primitive child")
        data_type = {"ui4": "U4", "fp4": "F4"}.get(shapes[0].children[0].kind)
        if data_type is None:
            raise ValueError("Unsupported tutorial primitive; no datatype guessed")
        wkn = replace(
            variable.wkn,
            authority_status=WknAuthority.VERIFIED,
            authority=registry["authority"],
            scope=registry["scope"],
            provenance=(
                *variable.wkn.provenance,
                SourceProvenance(
                    source_document="examples/fictional-wkn.json",
                    source_path="/value",
                    path_kind="json_pointer",
                ),
            ),
        )
        variables.append(replace(variable, wkn=wkn, data_type=data_type))
    return replace(interface, status_variables=tuple(variables))


def main() -> None:
    old = prepare_demo_interface(load_interface(EXAMPLES / "machine-v1.xml").interface)
    new = prepare_demo_interface(load_interface(EXAMPLES / "machine-v2.xml").interface)
    changes = compare_interfaces(old, new)
    print(
        report_json(
            report_from_changes(
                changes,
                ReportSource("examples/machine-v1.xml", "E172-0225"),
                ReportSource("examples/machine-v2.xml", "E172-0225"),
            )
        ),
        end="",
    )


if __name__ == "__main__":
    main()
