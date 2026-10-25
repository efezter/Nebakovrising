"""Build the installed KCD2 mod package from src, with a backup and byte checks."""
from pathlib import Path
import os
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def replace_windows_exclusive(temporary, destination, backup):
    """Some installs allow file updates but deny rename; require exclusive access."""
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(destination), 0xC0000000, 0, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    payload = temporary.read_bytes()
    with os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY), "r+b") as stream:
        try:
            stream.write(payload)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            if stream.read() != payload:
                raise RuntimeError("Installed package byte verification failed")
        except BaseException:
            stream.seek(0)
            stream.write(backup.read_bytes())
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
            raise


def build():
    source = ROOT / "src"
    destination = ROOT / "Data/nebakovrising.pak"
    entries = sorted(p for p in source.rglob("*") if p.is_file())
    temporary = destination.with_suffix(".pak.tmp")
    expected = {p.relative_to(source).as_posix(): p for p in entries}
    backup = None
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
            for name, path in expected.items():
                package.write(path, name)
        with zipfile.ZipFile(temporary) as package:
            if package.testzip() is not None:
                raise RuntimeError("Package CRC verification failed")
            if len(package.namelist()) != len(expected) or set(package.namelist()) != set(expected):
                raise RuntimeError("Package file list does not match src")
            for name, path in expected.items():
                if package.read(name) != path.read_bytes():
                    raise RuntimeError(f"Package content mismatch: {name}")
        if destination.exists():
            descriptor, name = tempfile.mkstemp(prefix="nebakovrising-before-meal-fixes-", suffix=".pak.bak")
            os.close(descriptor)
            backup = Path(name)
            shutil.copy2(destination, backup)
        try:
            os.replace(temporary, destination)
        except PermissionError:
            if os.name != "nt" or backup is None:
                raise
            replace_windows_exclusive(temporary, destination, backup)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"Built and verified: {destination} ({len(entries)} files)")
    if backup:
        print(f"Previous package backup: {backup}")


if __name__ == "__main__":
    build()
