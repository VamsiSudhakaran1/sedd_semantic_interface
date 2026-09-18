# SEDD SEMANTIC INTERFACE

## MASTER BUILD CONTRACT + MODEL ROUTING + IMPLEMENTATION PROMPTS

Working repository name:

`sema-sedd`

Working product description:

**A local-first semantic explorer and comparison engine for semiconductor equipment interfaces represented by SEMI E172 SEDD files.**

The name is temporary.

---

# HOW TO RUN THESE PROMPTS

Run the prompts sequentially.

Do NOT submit multiple implementation prompts simultaneously.

Before every prompt, select the model specified in:

`MODEL`

and the reasoning level specified in:

`EFFORT`

The model designation inside these prompts is guidance for the human operator.

The coding agent must NOT claim it switched models merely because the prompt requested a model.

If the running environment exposes no programmatic model-switching capability, continue with the model actually selected in Codex.

Never silently substitute a weaker model and claim the requested model was used.

---

# MODEL STRATEGY

Use GPT-6 Astra where mistakes would contaminate the architecture or semantic correctness.

Use GPT-5.6 Sol where the architecture is already defined and the work is primarily implementation.

Primary principle:

```text
ASTRA
    architecture
    domain interpretation
    canonical semantics
    matching
    graph reasoning
    difficult debugging
    security
    hostile audit

SOL
    implementation
    CLI
    serialization
    reports
    UI
    documentation
    routine tests
    mechanical refactoring
```

Do not increase reasoning effort merely because a task is long.

Use higher effort where the task requires harder reasoning.

---

# MODEL ROUTING SUMMARY

| Prompt | Model       | Effort |
| ------ | ----------- | ------ |
| 0      | GPT-6 Astra | High   |
| 1      | GPT-5.6 Sol | Medium |
| 2      | GPT-6 Astra | High   |
| 3      | GPT-5.6 Sol | High   |
| 4      | GPT-6 Astra | High   |
| 5      | GPT-6 Astra | High   |
| 6      | GPT-5.6 Sol | High   |
| 7      | GPT-6 Astra | High   |
| 8      | GPT-6 Astra | High   |
| 9      | GPT-5.6 Sol | Medium |
| 10     | GPT-5.6 Sol | Medium |
| 11     | GPT-6 Astra | XHigh  |
| 12     | GPT-6 Astra | XHigh  |
| 13     | GPT-6 Astra | High   |
| 14     | GPT-5.6 Sol | High   |
| 15     | GPT-5.6 Sol | High   |
| 16     | GPT-5.6 Sol | Medium |
| 17     | GPT-5.6 Sol | High   |
| 18     | GPT-6 Astra | High   |
| 19     | GPT-5.6 Sol | High   |
| 20     | GPT-6 Astra | XHigh  |
| 21     | GPT-5.6 Sol | Medium |
| 22     | GPT-6 Astra | Max    |

If Astra usage becomes constrained, do NOT downgrade Prompts:

`4, 7, 8, 11, 12, 20, 22`

These are the highest-value Astra runs.

---

# PROMPT 0 — MASTER PRODUCT CONTRACT

MODEL: GPT-6 Astra
EFFORT: High

You are building a new software product.

Read this entire contract before changing or creating code.

Create:

`MASTER_PRODUCT_CONTRACT.md`

and treat it as an architectural invariant throughout development.

## PRODUCT PURPOSE

The product consumes one or more SEMI E172 SEDD XML documents and constructs a canonical semantic representation of the semiconductor equipment interface.

Its primary jobs are:

1. inspect a SEDD document;
2. resolve relationships between interface entities;
3. explore those relationships;
4. compare two interface versions semantically;
5. distinguish meaningful interface changes from XML/document-order noise;
6. explain downstream relationships affected by change;
7. generate machine-readable and human-readable reports.

The product is NOT merely an XML diff tool.

Its core intellectual object is:

`CanonicalEquipmentInterface`

Comparison operates over canonical models rather than XML documents directly.

## NON-GOALS

Do NOT turn this project into:

* SECS/GEM host software;
* equipment-side GEM implementation;
* HSMS stack;
* GEM simulator;
* GEM compliance tester;
* factory automation middleware;
* station controller;
* equipment controller;
* recipe management;
* validation/gating software;
* PASS/FAIL/BLOCK/HOLD system;
* risk-scoring system;
* certification product;
* generic XML diff;
* AI-first application.

## CORE PHILOSOPHY

The application must be:

* deterministic;
* explainable;
* local-first;
* offline-capable;
* read-only with respect to SEDD inputs;
* useful without AI;
* conservative when semantic identity is uncertain;
* explicit about unsupported and unknown information.

Never invent relationships.

Unknown is a legitimate state.

## STANDARDS ARCHITECTURE

Assume E172 evolves.

Never scatter revision-specific XML assumptions throughout the repository.

Required architecture:

```text
XML
 ↓
secure loader
 ↓
revision detection
 ↓
revision adapter
 ↓
canonical equipment-interface model
 ↓
graph / comparison / reporting
```

Initial target:

`E172-0225`

Future revisions must be implementable through additional adapters without rewriting:

* graph logic;
* matching;
* comparison;
* reporting;
* CLI;
* UI.

Do not reproduce paid SEMI standards prose.

Do not imply SEMI endorsement or certification.

## CANONICAL DOMAIN

Represent at least:

* Equipment metadata
* Status Variables
* Data Variables
* Equipment Constants
* Collection Events
* Alarms
* Remote Commands
* Remote Command Parameters
* Supported SECS Messages
* Variable Formats
* Default Reports
* Event/Report Links
* SEMI Standards metadata
* Well-Known Names
* descriptions
* provenance
* unresolved references
* unknown extensions

## RELATIONSHIPS

Support evidence-backed relationships including:

Collection Event → variables

Collection Event → state-transition metadata

Default Report → variables

Collection Event → default report

Alarm → set event

Alarm → clear event

Remote Command → parameters

Entity → WKN

Entity → standard

Variable → format

Supported Message → structure/metadata

Never create a relationship merely because it appears plausible.

## SEMANTIC IDENTITY

Identity matching must be deterministic.

Potential strong evidence:

* type + native identifier;
* official WKN;
* remote-command identity;
* stream/function identity;
* explicit SEDD reference.

Do NOT automatically fuzzy-match descriptions.

Do NOT use an LLM to establish semantic identity.

Every cross-version match must preserve its reason:

`NATIVE_ID`

`WELL_KNOWN_NAME`

`COMMAND_NAME`

`STREAM_FUNCTION`

etc.

## CHANGE MODEL

Support at least:

* ENTITY_ADDED
* ENTITY_REMOVED
* IMPLEMENTATION_ID_CHANGED
* WELL_KNOWN_NAME_CHANGED
* NAME_CHANGED
* DATA_TYPE_CHANGED
* FORMAT_CHANGED
* UNIT_CHANGED
* RANGE_CHANGED
* DEFAULT_CHANGED
* DESCRIPTION_CHANGED
* RELATIONSHIP_ADDED
* RELATIONSHIP_REMOVED
* REPORT_CONTENT_CHANGED
* EVENT_REPORT_LINK_CHANGED
* ALARM_EVENT_LINK_CHANGED
* COMMAND_PARAMETER_CHANGED
* MESSAGE_STRUCTURE_CHANGED
* STANDARD_METADATA_CHANGED
* UNKNOWN_CHANGE

Ignore:

* XML ordering;
* whitespace;
* attribute ordering.

## PROVENANCE

Entities and changes should retain:

* source document;
* source revision where available;
* XML path;
* source identifier;
* source line where available.

## SECURITY

Treat SEDD as untrusted XML.

Protect against:

* XXE;
* external entity resolution;
* external DTD fetching;
* entity-expansion attacks;
* excessive recursion;
* oversized inputs;
* malicious namespaces;
* HTML/script injection into generated reports.

No network request may occur while parsing.

## BASE TECHNOLOGY

Python 3.12+

Preferred repository layout:

```text
src/sema_sedd/
    adapters/
    model/
    parser/
    graph/
    compare/
    report/
    cli/

tests/
docs/
```

Use:

* strong typing;
* pytest;
* secure XML parsing;
* Ruff or equivalent;
* buildable Python package.

Target CLI:

```text
sedd inspect
sedd explore
sedd compare
sedd report
```

## CONTINUOUS QUALITY RULE

For every following prompt:

1. inspect existing code first;
2. preserve correct prior behavior;
3. implement only the requested increment;
4. add tests;
5. run the complete test suite;
6. fix regressions;
7. update documentation;
8. surface unknown/unsupported behavior explicitly.

Never finish a prompt knowingly leaving failing tests.

---

# PROMPT 1 — REPOSITORY FOUNDATION

MODEL: GPT-5.6 Sol
EFFORT: Medium

Read `MASTER_PRODUCT_CONTRACT.md`.

Create a production-quality Python project.

Implement:

* `pyproject.toml`;
* `src/sema_sedd`;
* tests;
* CLI entry point;
* typed exceptions;
* package metadata;
* linting;
* formatting;
* testing configuration.

Create modules:

```text
adapters/
model/
parser/
graph/
compare/
report/
cli/
```

Initial CLI:

```text
sedd --version
sedd --help
```

Add CI for:

* tests;
* linting;
* type checking;
* package build.

Acceptance:

* clean virtual-environment installation;
* CLI works;
* tests pass;
* lint passes;
* type checks pass;
* package builds.

---