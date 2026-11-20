import os
import time
import ctypes
import logging
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger("AssistantTarget")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# [v3, 03.11.2026] Окно, куда уходит фраза после слова «Ассистент» — приложение Claude (вкладка Code)
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _process_name(hwnd) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def find_window(title: str, exe: str) -> Optional[int]:
    """
    Видимое окно с заголовком title у процесса exe; из нескольких — самое большое (главное окно).
    """
    found = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value == title and _process_name(hwnd) == exe.lower():
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append(((rect.right - rect.left) * (rect.bottom - rect.top), hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return max(found)[1] if found else None


def activate_window(hwnd) -> bool:
    """
    Выводит окно на передний план. Windows запрещает фоновой программе забирать фокус,
    поэтому на время переключения подключаемся к потоку текущего активного окна.
    """
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    current = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    attached = bool(fg_thread and fg_thread != current and user32.AttachThreadInput(current, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(current, fg_thread, False)
    time.sleep(0.15)
    ok = user32.GetForegroundWindow() == hwnd
    if not ok:
        logger.warning("Окно Claude не вышло на передний план.")
    return ok
