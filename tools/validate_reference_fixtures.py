"""Offline developer check using user-supplied, fingerprinted reference schemas.

Requires the optional references extra. This is not an application XML loader.
"""

import argparse
import hashlib
import json
from pathlib import Path

from lxml import etree


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "tests/fixtures"
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    names = ["E172-0225-SEDD-Schema.xsd", "E173-0415-SECSIIMessageNotation-Schema.xsd"]
    schemas = {}
    hashes = {}
    for name, source in zip(names, ["schema", "message_schema"], strict=True):
        path = (args.references / name).resolve()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest["sources"][source]["sha256"]:
            raise ValueError(f"Reference fingerprint mismatch: {name}")
        schemas[path.as_uri()] = data
        hashes[name] = digest

    class LocalSchemasOnly(etree.Resolver):
        def resolve(self, url, public_id, context):
            if url not in schemas:
                raise OSError(f"External schema resolution denied: {url}")
            return self.resolve_string(schemas[url], context, base_url=url)

    xml_parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    xml_parser.resolvers.add(LocalSchemasOnly())
    schema_uri = (args.references / names[0]).resolve().as_uri()
    schema_tree = etree.fromstring(schemas[schema_uri], parser=xml_parser, base_url=schema_uri)
    if schema_tree.getroottree().docinfo.doctype:
        raise ValueError("Unexpected schema DTD")
    schema = etree.XMLSchema(schema_tree)
    results = []
    for record in manifest["fixtures"]:
        if record["kind"] != "e172-synthetic":
            continue
        path = (fixtures / record["path"]).resolve()
        if not path.is_relative_to(fixtures.resolve()):
            raise ValueError("Fixture path escapes inventory")
        data = path.read_bytes()
        tree = etree.fromstring(data, parser=xml_parser)
        if tree.getroottree().docinfo.doctype:
            raise ValueError("DTD fixture must not be schema-validated by this utility")
        valid = schema.validate(tree)
        results.append(
            {
                "path": record["path"],
                "sha256": hashlib.sha256(data).hexdigest(),
                "xsd_valid": valid,
                "expected_xsd_valid": record["expected_xsd_valid"],
                "errors": [e.message for e in schema.error_log],
            }
        )
    report = {
        "classification": "OBSERVED",
        "scope": "Synthetic fixture XSD validation only",
        "schemas": hashes,
        "lxml_version": etree.LXML_VERSION,
        "libxml_version": etree.LIBXML_VERSION,
        "results": results,
    }
    if args.sample is not None:
        data = args.sample.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != manifest["sources"]["sample"]["sha256"]:
            raise ValueError("Sample fingerprint differs from the evidence manifest")
        sample_result = {"sha256": digest, "well_formed": False, "xsd_valid": None}
        try:
            sample = etree.fromstring(data, parser=xml_parser)
            sample_result["well_formed"] = True
            sample_result["xsd_valid"] = schema.validate(sample)
        except etree.XMLSyntaxError as error:
            sample_result["first_error_line"] = error.position[0]
            sample_result["first_error_column"] = error.position[1]
        report["sample"] = sample_result
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    mismatches = [r["path"] for r in results if r["xsd_valid"] != r["expected_xsd_valid"]]
    if mismatches:
        raise SystemExit(f"Unexpected validation results: {mismatches}")
    print(f"{len(results)} fixture schema outcomes matched expectations.")


if __name__ == "__main__":
    main()
