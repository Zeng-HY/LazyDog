import ctypes
from ctypes import wintypes

from voiceanywhere.windows import NativeHotkeyFilter, WM_HOTKEY, parse_hotkey


class NativeMessage(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def test_hotkey_parser_supports_default_and_function_keys() -> None:
    assert parse_hotkey("Ctrl+Alt+Space").virtual_key == 0x20
    assert parse_hotkey("Ctrl+Shift+F12").virtual_key == 0x7B
    assert parse_hotkey("Ctrl+Alt+PgDown").virtual_key == 0x22
    assert parse_hotkey("Ctrl+Alt+Left").virtual_key == 0x25


def test_native_filter_dispatches_its_own_hotkey_message() -> None:
    hotkeys = NativeHotkeyFilter()
    received: list[str] = []
    hotkeys.triggered.connect(received.append)
    message = NativeMessage(message=WM_HOTKEY, wParam=NativeHotkeyFilter.MAIN_ID)
    handled, result = hotkeys.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
    assert handled is True
    assert result == 0
    assert received == ["main"]
