# Contributing

Read [MASTER_PRODUCT_CONTRACT.md](MASTER_PRODUCT_CONTRACT.md) and
[architecture](docs/architecture.md) before changing behavior. Follow
[installation](docs/installation.md), then:

```sh
python -m pip install -e ".[dev]"
```

## Make a focused change

Keep revision-specific assumptions in adapters. Domain objects stay XML-independent,
immutable, and strongly typed. Matching/resolution retain collisions and conflicting
evidence instead of choosing convenient targets. Preserve unknown extensions and
source/entity diagnostics. Use controlled errors and budgets for untrusted input,
fanout, and output generation.

Original fixtures must exclude private equipment data, standards prose, credentials,
and proprietary schemas. Tutorials go in `examples/`; parser fixtures in
`tests/fixtures/` require manifest/evidence bookkeeping. Label assumptions and do not
silently turn them into parser behavior. New revisions need reliable technical evidence.

## Verify

```sh
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
python tests/smoke_install.py
```

The smoke script installs the wheel from `dist/` into a fresh environment. CI is
configured for Windows/Linux and Python 3.12-3.14. If host policy blocks temporary
executables, record the limitation; do not claim success or change policy to finish.
An approved interpreter can provide additional installed-package verification.
Platform-specific skips must state their reason.

Add meaningful behavior/security regressions. Determinism tests permute inventories
without changing ordered protocol sequences. Count lookup/traversal work instead of
asserting fragile timings. [The profiler](tools/profile_hostile.py) creates original
large cases. Generated output belongs in ignored `work/`, unless deliberately
publishing documented measurements. Tutorial expectations need no external files.

## Describe the result

Explain the trigger, behavior, semantic evidence, checks, and material limitations.
Update user/API documentation and affected public schemas/snapshots. Keep uncertainty
explicit and execution status independent of findings.

Optional reference checks use `.[references]` and separately obtained schemas as
explained in [observations](docs/e172_observations.md). They must not become required
downloads for normal tests. Read [security](docs/security.md) for vulnerability reports
and [standards/licensing](docs/standards_licensing.md) before submitting reference material.
