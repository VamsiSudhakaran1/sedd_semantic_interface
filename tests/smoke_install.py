"""Install the wheel into a fresh venv and test from outside the source tree."""

import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    assert len(wheels) == 1, "Expected exactly one built wheel"
    with tempfile.TemporaryDirectory() as directory:
        env = Path(directory) / "env"
        venv.create(env, with_pip=True)
        scripts = env / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        command = scripts / ("sedd.exe" if os.name == "nt" else "sedd")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-index", str(wheels[0])], check=True
        )
        for executable in ([str(command)], [str(python), "-m", "sema_sedd"]):
            for flag in ("--help", "--version"):
                result = subprocess.run(
                    [*executable, flag], cwd=directory, capture_output=True, text=True, check=True
                )
                assert "sedd" in result.stdout
                assert not result.stderr
        subprocess.run(
            [
                str(python),
                "-c",
                "from importlib.resources import files; "
                "assert files('sema_sedd').joinpath('py.typed').is_file()",
            ],
            cwd=directory,
            check=True,
        )
    print("Isolated wheel installation and CLI checks passed.")


if __name__ == "__main__":
    main()
