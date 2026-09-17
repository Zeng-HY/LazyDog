"""Opt-in desktop test: VOICEANYWHERE_NATIVE_INPUT_TEST=1 uv run pytest -s tests/test_native_keyboard.py."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("VOICEANYWHERE_NATIVE_INPUT_TEST") != "1",
    reason="Requires an interactive desktop and temporarily focuses a test-only window",
)


def test_real_windows_unicode_and_paste():
    from PySide6.QtCore import QMimeData
    from PySide6.QtWidgets import QApplication
    import win32gui
    import win32con
    import time
    import win32api
    import win32process

    from voiceanywhere.windows import KeyboardInjector

    app = QApplication.instance() or QApplication([])
    clipboard = app.clipboard()
    previous = QMimeData()
    original = clipboard.mimeData()
    if original is not None:
        for fmt in original.formats():
            previous.setData(fmt, original.data(fmt))
    foreground = win32gui.GetForegroundWindow()
    hwnd = win32gui.CreateWindowEx(
        0, "EDIT", "", win32con.WS_POPUP | win32con.WS_VISIBLE
        | win32con.WS_BORDER | win32con.ES_MULTILINE,
        100, 100, 500, 200, 0, 0, 0, None,
    )

    def pump():
        for _ in range(30):
            win32gui.PumpWaitingMessages()
            time.sleep(0.01)

    try:
        # A shell-launched test may not own foreground activation rights.
        current_thread = win32api.GetCurrentThreadId()
        foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground)
        attached = current_thread != foreground_thread
        if attached:
            win32process.AttachThreadInput(current_thread, foreground_thread, True)
        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(current_thread, foreground_thread, False)
        pump()
        assert win32gui.GetForegroundWindow() == hwnd
        assert win32gui.GetFocus() == hwnd
        keyboard = KeyboardInjector()
        text = "中文 English 123 😀"
        assert keyboard.unicode_text(text)
        pump()
        assert win32gui.GetWindowText(hwnd) == text
        win32gui.SetWindowText(hwnd, "")
        clipboard.setText(text)
        assert win32gui.GetForegroundWindow() == hwnd
        assert keyboard.paste()
        pump()
        assert win32gui.GetWindowText(hwnd) == text
    finally:
        clipboard.setMimeData(previous)
        win32gui.DestroyWindow(hwnd)
        if win32gui.GetForegroundWindow() in (0, hwnd):
            try:
                win32gui.SetForegroundWindow(foreground)
            except Exception:
                pass
