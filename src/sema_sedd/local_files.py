"""Reject network, device, stream, and redirected filesystem paths before I/O."""

import ctypes
import os
import re
import stat
import sys
from pathlib import Path, PureWindowsPath

from sema_sedd.exceptions import InputError


def _remote_drive(anchor: str) -> bool:
    if sys.platform != "win32":
        return False
    get_type = ctypes.windll.kernel32.GetDriveTypeW
    get_type.argtypes = [ctypes.c_wchar_p]
    get_type.restype = ctypes.c_uint
    return bool(get_type(anchor or str(Path.cwd().anchor)) == 4)


def local_path(path: str | os.PathLike[str]) -> Path:
    """Validate a local path, including existing ancestors; allow ordinary relative paths."""
    raw = os.fspath(path)
    if (
        not raw
        or any(ord(char) < 32 for char in raw)
        or raw.replace("\\", "/").startswith("//")
        or "://" in raw
    ):
        raise InputError("Path must name a local regular file")
    try:
        raw.encode("utf-8")
        if os.name == "nt":
            windows = PureWindowsPath(raw)
            if (
                _remote_drive(windows.anchor if windows.drive else "")
                or (windows.drive and not windows.root)
                or any(
                    ":" in part
                    or re.fullmatch(
                        r"(?:CON|CONIN\$|CONOUT\$|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?",
                        part.rstrip(" ."),
                        re.IGNORECASE,
                    )
                    or part.endswith((" ", "."))
                    and part not in (".", "..")
                    for part in (windows.parts[1:] if windows.anchor else windows.parts)
                )
            ):
                raise InputError("Path must name a local regular file")
        source = Path(raw).absolute()
        # Inspect ancestors from root to leaf without following redirects.
        for part in (*reversed(source.parents), source):
            try:
                info = part.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise InputError("Filesystem links and reparse points are not supported")
        return source
    except (OSError, ValueError, UnicodeError) as error:
        raise InputError("Unable to access local file path") from error
