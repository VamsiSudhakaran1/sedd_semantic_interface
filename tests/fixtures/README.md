# Synthetic fixture inventory

See [the observations](../../docs/e172_observations.md) for evidence and limitations.

The E172 schema has been inspected. The TrackSys sample and imported E173 schema
are still absent. No fixture is claimed to have passed complete XSD validation.
`e172-*.xml` files are candidates derived from inspected declarations; the qualified
children candidate is deliberately invalid. The report candidate has a deliberately
unresolved VID 799. Other XML files test generic mechanics and use generic names or
the unrelated `urn:sema-sedd:fixture-only:1` namespace.

JSON files are pending scenario plans, not canonical serialization. The reused IDs
in variables-plan are an adversarial cross-category collision, not a valid baseline.
`manifest.json` lists all inputs and evidence. The malformed folder includes both
syntax errors and well-formed adversarial inputs. Never expand its entities or
execute report text. Runtime parsing/security behavior remains unimplemented.
