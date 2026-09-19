"""Install the wheel into a fresh venv and test from outside the source tree."""

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=root / "dist")
    args = parser.parse_args()
    wheels = list(args.dist_dir.resolve().glob("*.whl"))
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
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.parser import load_sedd; "
                "import sys; "
                "assert load_sedd(sys.argv[1]).root.tag == "
                "'{urn:semi-org:xsd.SEDD}DataDictionary'",
                str(root / "tests" / "fixtures" / "minimal" / "e172-empty.xml"),
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.model import EquipmentInterface, StatusVariable, "
                "to_canonical_json; import json; "
                "data = json.loads(to_canonical_json(EquipmentInterface("
                "status_variables=(StatusVariable(key='sv', implementation_id='007'),)))); "
                "assert data['interface']['status_variables'][0]['implementation_id'] == '007'",
            ],
            cwd=directory,
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-c",
                "from sema_sedd.adapters import load_interface; "
                "from sema_sedd.model import to_canonical_json; import sys; "
                "result = load_interface(sys.argv[1], revision='E172-0225'); "
                "assert result.interface.equipment.model == 'Lantern17'; "
                "assert to_canonical_json(result.interface)",
                str(root / "tests" / "fixtures" / "minimal" / "e172-empty.xml"),
            ],
            cwd=directory,
            check=True,
        )
    print("Isolated installation, CLI, loader, model, and adapter checks passed.")


if __name__ == "__main__":
    main()
