import ctypes

import pytest

from voiceanywhere import windows as win


def test_input_matches_windows_abi():
    x64 = ctypes.sizeof(ctypes.c_void_p) == 8
    assert ctypes.sizeof(win.INPUT) == (40 if x64 else 28)
    assert ctypes.sizeof(win.MOUSEINPUT) == (32 if x64 else 24)
    assert win.INPUT.union.offset == (8 if x64 else 4)


def capture_send(monkeypatch, sent=None, error=0):
    calls = []

    def send(count, pointer, size):
        array = ctypes.cast(pointer, ctypes.POINTER(win.INPUT))
        calls.append((size, [(array[i].type, array[i].union.ki.wVk,
                              array[i].union.ki.wScan, array[i].union.ki.dwFlags)
                             for i in range(count)]))
        ctypes.set_last_error(error)
        return count if sent is None else sent

    monkeypatch.setattr(win.user32, "SendInput", send)
    return calls


def test_paste_event_order_and_native_size(monkeypatch):
    calls = capture_send(monkeypatch)
    assert win.KeyboardInjector().paste()
    assert calls == [(ctypes.sizeof(win.INPUT), [
        (1, 0x11, 0, 0), (1, 0x56, 0, 0),
        (1, 0x56, 0, 2), (1, 0x11, 0, 2),
    ])]


def test_unicode_utf16_surrogate_pairs_and_empty_text(monkeypatch):
    calls = capture_send(monkeypatch)
    keyboard = win.KeyboardInjector()
    assert keyboard.unicode_text("")
    assert calls == []
    assert keyboard.unicode_text("中😀")
    assert calls[0][1] == [
        (1, 0, 0x4E2D, 4), (1, 0, 0x4E2D, 6),
        (1, 0, 0xD83D, 4), (1, 0, 0xD83D, 6),
        (1, 0, 0xDE00, 4), (1, 0, 0xDE00, 6),
    ]


def test_failure_records_error_without_text(monkeypatch, caplog):
    capture_send(monkeypatch, sent=0, error=87)
    assert not win.KeyboardInjector().unicode_text("private transcript")
    assert "winerror=87" in caplog.text
    assert "private transcript" not in caplog.text


def test_last_error_is_cleared_before_send(monkeypatch, caplog):
    monkeypatch.setattr(win.user32, "SendInput", lambda *_: 0)
    ctypes.set_last_error(87)
    assert not win.KeyboardInjector().paste()
    assert "winerror=0" in caplog.text


@pytest.mark.parametrize("operation", ["paste", "unicode"])
def test_partial_input_stops_replay_and_releases_keys(monkeypatch, operation):
    calls = capture_send(monkeypatch, sent=1)
    keyboard = win.KeyboardInjector()
    with pytest.raises(win.PartialInputError):
        keyboard.paste() if operation == "paste" else keyboard.unicode_text("中")
    assert len(calls) == 2
    assert all(event[3] & win.KEYEVENTF_KEYUP for event in calls[1][1])
