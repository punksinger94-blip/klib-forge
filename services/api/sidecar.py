from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

import uvicorn
from klib_api.main import app


def _exit_with_parent(parent_pid: int) -> None:
    if os.name == "nt":
        synchronize = 0x00100000
        infinite = 0xFFFFFFFF
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, parent_pid)
        if not handle:
            return
        try:
            kernel32.WaitForSingleObject(handle, infinite)
        finally:
            kernel32.CloseHandle(handle)
        os._exit(0)

    while True:
        try:
            os.kill(parent_pid, 0)
        except ProcessLookupError:
            os._exit(0)
        except PermissionError:
            return
        time.sleep(0.5)


def watch_parent() -> None:
    parent_pid = os.getenv("KLIB_PARENT_PID")
    if not parent_pid:
        return
    threading.Thread(
        target=_exit_with_parent,
        args=(int(parent_pid),),
        name="klib-parent-watch",
        daemon=True,
    ).start()


def main() -> None:
    watch_parent()
    uvicorn.run(
        app,
        host=os.getenv("KLIB_API_HOST", "127.0.0.1"),
        port=int(os.getenv("KLIB_API_PORT", "8000")),
        log_level=os.getenv("KLIB_API_LOG_LEVEL", "warning"),
        access_log=False,
    )


if __name__ == "__main__":
    main()
