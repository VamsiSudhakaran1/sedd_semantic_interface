"""Reproduce a positional XML-tree baseline versus the canonical change engine.

Only original tracked synthetic fixtures are read. No external standards files,
network operations, or claim of official registry verification are involved.
"""

import argparse
import difflib
import json
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from typing import Any

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.model import EquipmentInterface, SourceProvenance, WknAuthority


def xml_tree_deltas(before: bytes, after: bytes) -> list[dict[str, object]]:
    """Namespace-aware positional baseline; attributes ignore order and parent
    indentation is ignored. Unlike semantic matching it has no equipment identities.
    """

    def flatten(root: ET.Element) -> dict[str, object]:
        values: dict[str, object] = {}

        def visit(node: ET.Element, path: str) -> None:
            values[path + "/tag"] = node.tag
            values[path + "/attributes"] = dict(node.attrib)
            values[path + "/text"] = (
                node.text if not len(node) or (node.text or "").strip() else None
            )
            for index, child in enumerate(node):
                visit(child, f"{path}/{index}")

        visit(root, "")
        return values

    old, new = flatten(ET.fromstring(before)), flatten(ET.fromstring(after))
    return [
        {"path": key, "old": old.get(key), "new": new.get(key)}
        for key in sorted(old.keys() | new.keys())
        if old.get(key) != new.get(key)
    ]


def verify_fictional_wkn(interface: EquipmentInterface) -> EquipmentInterface:
    variables = []
    for variable in interface.status_variables:
        assert variable.wkn is not None
        variables.append(
            replace(
                variable,
                wkn=replace(
                    variable.wkn,
                    authority="fictional-registry",
                    scope="demo",
                    authority_status=WknAuthority.VERIFIED,
                    provenance=(SourceProvenance(source_document="synthetic-registry.json"),),
                ),
            )
        )
    return replace(interface, status_variables=tuple(variables))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parents[1] / "tests/fixtures"
    original = (fixtures / "relationships/e172-complete.xml").read_bytes()
    root = ET.fromstring(original)
    events = root.find("CollectionEvents")
    assert events is not None
    events[:] = list(reversed(list(events)))
    for node in root.iter():
        attributes = tuple(node.attrib.items())
        node.attrib.clear()
        node.attrib.update(reversed(attributes))
    ET.indent(root, space="    ")
    noise = ET.tostring(root, encoding="utf-8")
    renumbered = original.replace(b"<SVID>702</SVID>", b"<SVID>1702</SVID>").replace(
        b"<VID>702</VID>", b"<VID>1702</VID>"
    )
    inputs = [
        ("inventory_and_serialization_noise", noise, False),
        ("description_only", (fixtures / "changes/e172-description.xml").read_bytes(), False),
        ("alarm_clear_target", (fixtures / "changes/e172-alarm-clear.xml").read_bytes(), False),
        ("report_variable_target", (fixtures / "changes/e172-report.xml").read_bytes(), False),
        ("verified_wkn_id_continuity", renumbered, True),
    ]
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        before_path, after_path = Path(directory) / "old.xml", Path(directory) / "new.xml"
        before_path.write_bytes(original)
        for name, after, verified in inputs:
            after_path.write_bytes(after)
            old = load_interface(before_path, revision="E172-0225").interface
            new = load_interface(after_path, revision="E172-0225").interface
            if verified:
                old, new = verify_fictional_wkn(old), verify_fictional_wkn(new)
            changes = compare_interfaces(old, new)
            text_lines = list(
                difflib.unified_diff(original.decode().splitlines(), after.decode().splitlines())
            )
            results.append(
                {
                    "case": name,
                    "fictional_registry_claim_supplied": verified,
                    "raw_text_changed_lines": sum(
                        line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
                        for line in text_lines
                    ),
                    "positional_xml_deltas": xml_tree_deltas(original, after),
                    "semantic_changes": [
                        {
                            "entity_type": change.entity_type.value,
                            "old_id": change.old_entity.implementation_id
                            if change.old_entity
                            else None,
                            "new_id": change.new_entity.implementation_id
                            if change.new_entity
                            else None,
                            "kinds": [kind.value for kind in change.kinds],
                            "categories": [category.value for category in change.categories],
                            "matching_strategy": change.match.strategy.value
                            if change.match
                            else None,
                            "properties": [p.field for p in change.properties],
                            "relationships": [
                                {
                                    "field": r.field,
                                    "kind": r.kind.value,
                                    "added": len(r.added),
                                    "removed": len(r.removed),
                                    "order_changed": r.order_changed,
                                }
                                for r in change.relationships
                            ],
                        }
                        for change in changes.entity_changes
                    ],
                    "is_complete": changes.is_complete,
                    "issue_kinds": sorted({issue.kind.value for issue in changes.issues}),
                }
            )
    args.output.write_text(
        json.dumps(
            {
                "baseline": (
                    "Namespace-aware positional XML tree comparison; attribute order and "
                    "parent indentation ignored. Not an identity-aware XML edit-distance algorithm."
                ),
                "registry_note": (
                    "The continuity example supplies fictional verification evidence to canonical "
                    "models. XML WKN text alone is unverified."
                ),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(
            f"{result['case']}: text={result['raw_text_changed_lines']}, "
            f"XML={len(result['positional_xml_deltas'])}, "
            f"semantic={len(result['semantic_changes'])}"
        )


if __name__ == "__main__":
    main()
