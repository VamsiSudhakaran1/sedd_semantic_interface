# Limitations

Only evidenced E172-0225 structures have a default adapter. Hints select an adapter;
runtime loading does not perform XSD validation or establish standards conformance.
Other revisions require evidence-backed adapters.

Raw XML WKNs are `UNVERIFIED`. Equal strings alone cannot establish continuity after
an ID change. Canonical callers can supply authority, scope, verification status,
and provenance; the API cannot authenticate a registry. The fictional tutorial
exercises this evidence contract, not official verification. Native IDs may be reused
by suppliers, so matching remains an exact application policy rather than proof of
lineage. Callers choose the interface lineage to compare.

Variable datatypes are represented through named format references and structures.
The E172 adapter does not populate scalar `data_type` for arbitrary formats. Detailed
numeric, encoding, length-expression, enum/bit-field, and compound semantics remain
incomplete. Some event VID target-kind rules are pending; those references remain
unresolved. Unknown extensions can make comparison incomplete even when unchanged.

Inventory and attribute order are ignored, while protocol sequences, report-member
order, repeated members, and exact scalar text remain meaningful. Whitespace in names
or descriptions is not automatically normalized. No confirmed changes can coexist
with incomplete identity/reference evidence.

[Resource ceilings](security.md) can reject valid exceptionally large inputs/reports.
Large HTML can be expensive for browsers; browser performance was not measured in the
[CLI audit](security_performance_audit.md). The tool produces no compatibility/risk score,
operational-failure prediction, or certification. Exit status describes execution only.

Original supplied schemas/sample are excluded and optional for additional validation.
Examples and required coverage need no proprietary files. Reports embed source paths;
consider that when sharing them. CI is configured for Linux/Windows, but Linux runtime
execution was not performed in the local Windows audit. Platform tests can skip when
the operating system or host policy lacks the capability.
