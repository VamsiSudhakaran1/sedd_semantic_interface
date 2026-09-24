# Local HTML comparison report

Generate a self-contained report with:

```sh
sedd report before.xml after.xml --html report.html
```

Open `report.html` in a browser. The page contains all styles, the small filter
script, and the comparison data. It loads no external assets and makes no network
requests. There is no backend, account, or telemetry. The generated file is local;
the command does not open a browser or upload the SEDD inputs.

The top summary shows confirmed matches, changed entities, additions, removals,
interface and documentation changes, unresolved items, and diagnostics. Search
matches changed entity text, including IDs, names, change codes, and evidence.
The change filter selects additions, removals, interface, property, relationship,
documentation, or unknown changes. The documentation checkbox hides or shows
documentation rows independently. Controls operate entirely in the browser.
With scripts disabled, the complete report remains readable: expand an entity
with its native HTML disclosure control.

Each changed entity shows its before/after values, exact matching strategy and
evidence where a match was confirmed, source locations, and factual dependency
context on both sides. Relationship changes show added and removed members.
Unresolved matches and references remain separate from confirmed changes; an
incomplete comparison is marked clearly. Diagnostics include source-side labels
and available provenance. Dependency counts are graph observations, not risk
scores or claims that applications will fail.

The report uses HTML escaping for all source-derived text. Its Content Security
Policy blocks network connections and allows only the bundled inline script by
hash. The output destination must differ from both input paths. The CLI returns
zero when report generation succeeds, regardless of how many changes are found;
invalid inputs or output failures return a command error.

The report presents the [versioned JSON report contract](json_report_contract.md)
and canonical comparison model without changing that contract. The page is
intended for human review, while integrations should use the JSON report API.
