"""Opt-in, reversible Windows autostart through HKCU Run. No admin rights, no scheduled tasks.

The user turns it on and off explicitly. Disabling removes only Guardian's own value.
"""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OpenTutorGuardian"


def build_command(repo_root: Path, python_exe: str | None = None) -> str:
    """Command line that starts Guardian hidden in the tray, from any working directory."""
    exe = Path(python_exe or sys.executable)
    windowless = exe.with_name("pythonw.exe")
    if windowless.exists():
        exe = windowless
    code = f"import sys; sys.path.insert(0, r'{repo_root}'); from guardian_mvp.desktop import main; main()"
    return f'"{exe}" -c "{code}" --hidden'


def _winreg():
    if sys.platform != "win32":
        raise OSError("Autostart is only available on Windows")
    import winreg
    return winreg


def is_enabled(run_key: str = RUN_KEY) -> bool:
    try:
        wr = _winreg()
        with wr.OpenKey(wr.HKEY_CURRENT_USER, run_key) as key:
            wr.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def enable(repo_root: Path, run_key: str = RUN_KEY) -> None:
    wr = _winreg()
    with wr.CreateKey(wr.HKEY_CURRENT_USER, run_key) as key:
        wr.SetValueEx(key, VALUE_NAME, 0, wr.REG_SZ, build_command(repo_root))


def disable(run_key: str = RUN_KEY) -> None:
    try:
        wr = _winreg()
        with wr.OpenKey(wr.HKEY_CURRENT_USER, run_key, 0, wr.KEY_SET_VALUE) as key:
            wr.DeleteValue(key, VALUE_NAME)
    except OSError:
        pass  # already off
