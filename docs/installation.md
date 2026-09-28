# Installation

Use Python 3.12+ built with Expat 2.7.2+. There are no third-party runtime dependencies.
Git is needed only to obtain a checkout. Run these commands in the checkout:

```sh
git clone https://github.com/VamsiSudhakaran1/sedd_semantic_interface.git
cd sedd_semantic_interface
python -c "from xml.parsers import expat; print(expat.EXPAT_VERSION)"
```

## Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\sedd.exe --help
.\.venv\Scripts\python.exe -m sema_sedd --version
```

Activation is optional. If permitted, run `.\.venv\Scripts\Activate.ps1`, then use
`python` and `sedd` directly. For development use `pip install -e ".[dev]"`.
A host blocking newly created executables needs an approved Python environment or
administrator-approved deployment. This project cannot change host policy.

## POSIX shell

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
sedd --help
python -m sema_sedd --version
```

## Wheels and offline installation

```sh
python -m pip install -e ".[dev]"
python -m build
python -m pip install dist/sema_sedd-0.1.0-py3-none-any.whl
```

For offline installation, copy a built wheel to the target and use
`python -m pip install --no-index /path/to/sema_sedd-0.1.0-py3-none-any.whl`.
Acquiring Python/build tools and downloading dependencies are setup operations;
installed inspection, exploration, comparison, and reporting operate offline.
Examples are included in the repository/source distribution, not the runtime wheel;
copy `examples/` separately when using a wheel.

## Check and troubleshoot

```sh
sedd --version
sedd inspect examples/machine-v1.xml --json
```

If `sedd` is absent from PATH, use its full environment path or `python -m sema_sedd`.
An unsafe Expat error requires a patched Python runtime meeting the minimum above.
Unsupported revision errors require a supported file or an evidence-backed adapter;
renaming a schema file cannot establish support. See [supported revisions](supported_revisions.md).
