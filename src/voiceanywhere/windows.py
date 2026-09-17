from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

from voiceanywhere.models import DeliveryResult, TargetSnapshot


if os.name != "nt":  # pragma: no cover - the product itself is Windows-only
    raise RuntimeError("VoiceAnywhere P0 only supports Windows")


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_ESCAPE = 0x1B
GWL_STYLE = -16
ES_PASSWORD = 0x0020
CF_TEXT = 1
CF_OEMTEXT = 7
CF_UNICODETEXT = 13
CF_LOCALE = 16
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
LLKHF_INJECTED = 0x10
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def _configure_apis() -> None:
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
    user32.EnumClipboardFormats.restype = wintypes.UINT
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.restype = wintypes.HANDLE


_configure_apis()


def _window_text(hwnd: int) -> str:
    if not hwnd:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _focused_hwnd(foreground_hwnd: int) -> int:
    process_id = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(process_id))
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if thread_id and user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return int(info.hwndFocus or 0)
    return 0


def _process_name(process_id: int) -> str:
    handle = kernel32.OpenProcess(0x1000, False, process_id)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32_768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value).lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


class UiAutomationInspector:
    """Optional UIA password check. Failure is deliberately non-fatal for normal inputs."""

    def __init__(self) -> None:
        self._automation = None
        try:
            import comtypes.client

            self._automation = comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")
        except Exception:
            self._automation = None

    def focused_is_password(self) -> bool:
        if self._automation is None:
            return False
        try:
            return bool(self._automation.GetFocusedElement().CurrentIsPassword)
        except Exception:
            return False


class TargetManager:
    def __init__(self, ui_automation: UiAutomationInspector | None = None) -> None:
        self.ui_automation = ui_automation or UiAutomationInspector()

    def capture(self) -> TargetSnapshot:
        foreground = int(user32.GetForegroundWindow() or 0)
        if not foreground:
            raise RuntimeError("未找到当前输入窗口")
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
        focus = _focused_hwnd(foreground)
        class_name = _window_text(focus)
        style = int(user32.GetWindowLongPtrW(focus, GWL_STYLE) or 0) if focus else 0
        is_password = bool(style & ES_PASSWORD) or self.ui_automation.focused_is_password()
        app_style = self._app_style(_process_name(process_id.value))
        return TargetSnapshot(
            foreground_hwnd=foreground,
            process_id=process_id.value,
            focus_hwnd=focus,
            focus_class=class_name,
            is_password=is_password,
            app_style=app_style,
        )

    def is_still_target(self, snapshot: TargetSnapshot) -> bool:
        foreground = int(user32.GetForegroundWindow() or 0)
        if foreground != snapshot.foreground_hwnd:
            return False
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
        if process_id.value != snapshot.process_id:
            return False
        focus = _focused_hwnd(foreground)
        if snapshot.focus_hwnd and focus and focus != snapshot.focus_hwnd:
            return False
        if self.ui_automation.focused_is_password():
            return False
        return True

    @staticmethod
    def _app_style(process_name: str) -> str:
        if "wechat" in process_name or "weixin" in process_name:
            return "chat"
        if "outlook" in process_name:
            return "email"
        return "neutral"


class Clipboard:
    """Uses only an empty clipboard or a clipboard containing pure Windows text formats."""

    def snapshot_text(self) -> tuple[int, str | None] | None:
        if not user32.OpenClipboard(None):
            return None
        try:
            formats: set[int] = set()
            current = 0
            while True:
                current = user32.EnumClipboardFormats(current)
                if not current:
                    break
                formats.add(int(current))
            if not formats:
                return user32.GetClipboardSequenceNumber(), None
            if not formats.issubset({CF_TEXT, CF_OEMTEXT, CF_UNICODETEXT, CF_LOCALE}):
                return None
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return None
            try:
                text = ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
            return user32.GetClipboardSequenceNumber(), text
        finally:
            user32.CloseClipboard()

    def set_text(self, text: str) -> int | None:
        if not user32.OpenClipboard(None):
            return None
        try:
            if not user32.EmptyClipboard():
                return None
            raw = (text + "\0").encode("utf-16-le")
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
            if not handle:
                return None
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                return None
            ctypes.memmove(pointer, raw, len(raw))
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                return None
            return int(user32.GetClipboardSequenceNumber())
        finally:
            user32.CloseClipboard()

    def restore_text(self, prior_text: str | None, expected_sequence: int) -> bool:
        if int(user32.GetClipboardSequenceNumber()) != expected_sequence:
            return False
        if prior_text is None:
            if not user32.OpenClipboard(None):
                return False
            try:
                return bool(user32.EmptyClipboard())
            finally:
                user32.CloseClipboard()
        return self.set_text(prior_text) is not None


class KeyboardInjector:
    def paste(self) -> bool:
        inputs = (INPUT * 4)(
            INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0x11, 0, 0, 0, 0))),
            INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0x56, 0, 0, 0, 0))),
            INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0x56, 0, KEYEVENTF_KEYUP, 0, 0))),
            INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0x11, 0, KEYEVENTF_KEYUP, 0, 0))),
        )
        return user32.SendInput(len(inputs), ctypes.byref(inputs), ctypes.sizeof(INPUT)) == len(inputs)

    def unicode_text(self, text: str) -> bool:
        inputs: list[INPUT] = []
        units = [int.from_bytes(text.encode("utf-16-le")[index:index + 2], "little") for index in range(0, len(text.encode("utf-16-le")), 2)]
        for unit in units:
            inputs.extend([
                INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, 0))),
                INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))),
            ])
        if not inputs:
            return True
        array = (INPUT * len(inputs))(*inputs)
        return user32.SendInput(len(array), ctypes.byref(array), ctypes.sizeof(INPUT)) == len(array)


class DeliveryService:
    def __init__(self, target_manager: TargetManager, clipboard: Clipboard, keyboard: KeyboardInjector) -> None:
        self.target_manager = target_manager
        self.clipboard = clipboard
        self.keyboard = keyboard

    def deliver(self, target: TargetSnapshot, text: str) -> DeliveryResult:
        if not self.target_manager.is_still_target(target):
            if self.clipboard.set_text(text) is not None:
                return DeliveryResult(False, "输入目标已变化，结果已复制，可直接粘贴")
            return DeliveryResult(False, "输入目标已变化，且无法写入剪贴板")
        snapshot = self.clipboard.snapshot_text()
        if snapshot is None:
            # A rich clipboard cannot be restored faithfully. Do not replace it:
            # type directly into the still-valid foreground control instead.
            if self.keyboard.unicode_text(text):
                return DeliveryResult(True)
            # Some applications reject Unicode key events but accept Ctrl+V. In
            # that case, use the result clipboard as a last delivery path and
            # paste immediately; it cannot retain the rich clipboard content.
            if self.target_manager.is_still_target(target):
                if self.clipboard.set_text(text) is not None:
                    if self.keyboard.paste():
                        return DeliveryResult(True)
                    return DeliveryResult(False, "未能插入文字，结果已复制，可直接粘贴")
            elif self.clipboard.set_text(text) is not None:
                return DeliveryResult(False, "输入目标已变化，结果已复制，可直接粘贴")
            return DeliveryResult(False, "无法插入或写入剪贴板，结果已保留")
        _prior_sequence, prior_text = snapshot
        temporary_sequence = self.clipboard.set_text(text)
        if temporary_sequence is None:
            if self.target_manager.is_still_target(target) and self.keyboard.unicode_text(text):
                return DeliveryResult(True)
            return DeliveryResult(False, "无法安全使用剪贴板，结果已保留，请点击复制")
        if not self.target_manager.is_still_target(target):
            return DeliveryResult(False, "输入目标已变化，结果已复制，可直接粘贴")
        if not self.keyboard.paste():
            if self.target_manager.is_still_target(target) and self.keyboard.unicode_text(text):
                return DeliveryResult(True)
            return DeliveryResult(False, "未能插入文字，结果已复制，可直接粘贴")
        time.sleep(0.15)
        self.clipboard.restore_text(prior_text, temporary_sequence)
        return DeliveryResult(True)

    def copy_to_clipboard(self, text: str) -> bool:
        return bool(text) and self.clipboard.set_text(text) is not None


class InputActivityMonitor:
    """Global hook records one boolean only; it never stores text, keys, or click positions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._available = False
        self._active = False
        self._invalidated = False
        self._ignore_until = 0.0
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc = HOOKPROC(self._keyboard_callback)
        self._mouse_proc = HOOKPROC(self._mouse_callback)

    def install(self) -> bool:
        module = kernel32.GetModuleHandleW(None)
        self._keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, ctypes.cast(self._keyboard_proc, ctypes.c_void_p), module, 0
        )
        self._mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL, ctypes.cast(self._mouse_proc, ctypes.c_void_p), module, 0
        )
        self._available = bool(self._keyboard_hook and self._mouse_hook)
        if not self._available:
            self.uninstall()
        return self._available

    def uninstall(self) -> None:
        for hook in (self._keyboard_hook, self._mouse_hook):
            if hook:
                user32.UnhookWindowsHookEx(hook)
        self._keyboard_hook = self._mouse_hook = None
        self._available = False

    def begin(self, ignore_seconds: float = 0.35) -> None:
        with self._lock:
            self._active = True
            self._invalidated = not self._available
            self._ignore_until = time.monotonic() + ignore_seconds

    def ignore_input_for(self, seconds: float = 0.35) -> None:
        with self._lock:
            self._ignore_until = time.monotonic() + seconds

    def end(self) -> None:
        with self._lock:
            self._active = False

    @property
    def invalidated(self) -> bool:
        with self._lock:
            return self._invalidated

    @property
    def available(self) -> bool:
        with self._lock:
            return self._available

    def _mark_activity(self, injected: bool = False) -> None:
        if injected:
            return
        with self._lock:
            if self._active and time.monotonic() >= self._ignore_until:
                self._invalidated = True

    def _keyboard_callback(self, code: int, _w_param: int, l_param: int) -> int:
        if code == HC_ACTION and l_param:
            event = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            self._mark_activity(bool(event.flags & LLKHF_INJECTED))
        return user32.CallNextHookEx(self._keyboard_hook, code, _w_param, l_param)

    def _mouse_callback(self, code: int, _w_param: int, _l_param: int) -> int:
        interaction_messages = {0x0201, 0x0204, 0x0207, 0x020B, 0x020A}  # down, X down, wheel
        if code == HC_ACTION and _w_param in interaction_messages:
            self._mark_activity(False)
        return user32.CallNextHookEx(self._mouse_hook, code, _w_param, _l_param)


@dataclass(frozen=True)
class ParsedHotkey:
    modifiers: int
    virtual_key: int


def parse_hotkey(value: str) -> ParsedHotkey:
    mapping = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
    keys = [part.strip() for part in value.split("+") if part.strip()]
    if len(keys) < 2:
        raise ValueError("快捷键至少要有一个修饰键和一个按键，例如 Ctrl+Alt+Space")
    modifiers = 0
    for key in keys[:-1]:
        try:
            modifiers |= mapping[key.lower()]
        except KeyError as exc:
            raise ValueError(f"不支持的修饰键：{key}") from exc
    final = keys[-1].upper()
    if final == "SPACE":
        virtual_key = 0x20
    elif len(final) == 1 and ("A" <= final <= "Z" or "0" <= final <= "9"):
        virtual_key = ord(final)
    elif final.startswith("F") and final[1:].isdigit() and 1 <= int(final[1:]) <= 24:
        virtual_key = 0x70 + int(final[1:]) - 1
    else:
        special_keys = {
            "BACKSPACE": 0x08,
            "TAB": 0x09,
            "RETURN": 0x0D,
            "ENTER": 0x0D,
            "ESC": 0x1B,
            "ESCAPE": 0x1B,
            "PGUP": 0x21,
            "PAGEUP": 0x21,
            "PGDOWN": 0x22,
            "PAGEDOWN": 0x22,
            "END": 0x23,
            "HOME": 0x24,
            "LEFT": 0x25,
            "UP": 0x26,
            "RIGHT": 0x27,
            "DOWN": 0x28,
            "INS": 0x2D,
            "INSERT": 0x2D,
            "DEL": 0x2E,
            "DELETE": 0x2E,
        }
        if final not in special_keys:
            raise ValueError("该主按键暂不支持。请使用字母、数字、Space、F 键、方向键或常用编辑键。")
        virtual_key = special_keys[final]
    return ParsedHotkey(modifiers, virtual_key)


class NativeHotkeyFilter(QObject, QAbstractNativeEventFilter):
    triggered = Signal(str)

    MAIN_ID = 0x5641
    CANCEL_ID = 0x5642

    def __init__(self) -> None:
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self._main_registered = False
        self._main_text: str | None = None
        self._cancel_registered = False

    def register_main(self, text: str) -> None:
        self.unregister_main()
        hotkey = parse_hotkey(text)
        if not user32.RegisterHotKey(None, self.MAIN_ID, hotkey.modifiers, hotkey.virtual_key):
            raise RuntimeError("快捷键无法注册，可能已被其他程序占用")
        self._main_registered = True
        self._main_text = text

    def replace_main(self, text: str) -> None:
        """Replace a global hotkey without leaving the old one disabled on failure."""
        if text == self._main_text:
            return
        previous = self._main_text
        self.unregister_main()
        try:
            self.register_main(text)
        except Exception:
            if previous:
                self.register_main(previous)
            raise

    def unregister_main(self) -> None:
        if self._main_registered:
            user32.UnregisterHotKey(None, self.MAIN_ID)
        self._main_registered = False
        self._main_text = None

    def register_cancel(self) -> bool:
        if self._cancel_registered:
            return True
        self._cancel_registered = bool(user32.RegisterHotKey(None, self.CANCEL_ID, 0, VK_ESCAPE))
        return self._cancel_registered

    def unregister_cancel(self) -> None:
        if self._cancel_registered:
            user32.UnregisterHotKey(None, self.CANCEL_ID)
        self._cancel_registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt interface name
        if bytes(event_type) not in {b"windows_generic_MSG", b"windows_dispatcher_MSG"}:
            return False, 0
        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT),
            ]
        msg = MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            if msg.wParam == self.MAIN_ID:
                self.triggered.emit("main")
                return True, 0
            if msg.wParam == self.CANCEL_ID:
                self.triggered.emit("cancel")
                return True, 0
        return False, 0
