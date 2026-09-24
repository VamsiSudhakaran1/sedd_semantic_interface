# Single-file interface explorer

Generate an offline view of one SEDD interface:

```sh
sedd report equipment.xml --html interface.html
```

Open `interface.html` locally. It contains its styles, search script, and data in
one file. It has no backend, account, telemetry, or external assets. The command
does not open a browser or upload the input. For a comparison of two files, use
`sedd report OLD NEW --html report.html` instead.

The page has Overview, Variables, Events, Reports, Alarms, Remote Commands,
Messages, Standards/WKN, and Diagnostics sections. Overview shows equipment
metadata, provenance, and counts. Expand an entity to see its canonical
properties, source identifier, WKN with authority status, description, incoming
and outgoing relationships, and source locations. The Standards/WKN section also
has a WKN directory linking to each recorded entity. Command parameters appear
under Remote Commands and have explicit containment links to their command.

Search filters entities by identifier, name, WKN, or description; message S/F
identities and standard designations are searchable too. It runs only in the
local page. Without JavaScript, all entity cards remain available through native
HTML disclosure controls.

Relationship links appear only for resolved targets. Unresolved or ambiguous
references retain their selector and reason in the owner's outgoing list and in
Diagnostics; the page does not guess a target. Unknown extensions and adapter
diagnostics are also listed. Counts and links reflect the canonical model and
reference resolver, so missing or unsupported source material is not inferred.

All source-derived text is HTML escaped. A Content Security Policy blocks network
connections and permits only the bundled script by hash. The output path must
differ from the input path. Successful generation returns zero even if the
interface has unresolved references.
