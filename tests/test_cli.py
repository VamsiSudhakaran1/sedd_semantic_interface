"""Check the installed public command-line contract."""

import subprocess
import sys
from importlib.metadata import version

import pytest

from sema_sedd.cli import main
from sema_sedd.exceptions import (
    InputError,
    ReportError,
    SeddError,
    SemanticError,
    UnsupportedRevisionError,
    XmlSecurityError,
)


@pytest.mark.parametrize("args", [[], ["--help"], ["--version"]])
def test_module_cli(args: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sema_sedd", *args], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert result.stderr == ""
    if args == ["--version"]:
        assert result.stdout.strip() == f"sedd {version('sema-sedd')}"
    else:
        assert "--help" in result.stdout
        assert "--version" in result.stdout
        assert "not yet implemented" in " ".join(result.stdout.split())


@pytest.mark.parametrize("arg", ["inspect", "compare", "explore", "report", "--bogus", "--ver"])
def test_unsupported_arguments(arg: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main([arg])
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_no_argument_entry_point(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: sedd" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error_type",
    [InputError, XmlSecurityError, UnsupportedRevisionError, SemanticError, ReportError],
)
def test_typed_errors(error_type: type[SeddError]) -> None:
    error = error_type("context")
    assert isinstance(error, SeddError)
    assert str(error) == "context"
