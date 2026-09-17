from voiceanywhere.models import TargetSnapshot
from voiceanywhere.windows import DeliveryService


class FakeTargetManager:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def is_still_target(self, _target) -> bool:
        return self.valid


class FakeClipboard:
    def __init__(self, snapshot=(10, "old"), temporary=11) -> None:
        self.snapshot = snapshot
        self.temporary = temporary
        self.restores = []
        self.copied = []

    def snapshot_text(self):
        return self.snapshot

    def set_text(self, text):
        self.copied.append(text)
        return self.temporary

    def restore_text(self, text, sequence):
        self.restores.append((text, sequence))
        return True


class FakeKeyboard:
    def __init__(self, pasted: bool = True, unicode_inserted: bool = True) -> None:
        self.pasted = pasted
        self.unicode_inserted = unicode_inserted
        self.typed = []
        self.paste_calls = 0

    def paste(self) -> bool:
        self.paste_calls += 1
        return self.pasted

    def unicode_text(self, text: str) -> bool:
        self.typed.append(text)
        return self.unicode_inserted


TARGET = TargetSnapshot(1, 1)


def test_delivery_restores_plain_text_clipboard_after_one_paste() -> None:
    clipboard = FakeClipboard()
    service = DeliveryService(FakeTargetManager(), clipboard, FakeKeyboard())
    result = service.deliver(TARGET, "新的文字")
    assert result.inserted
    assert clipboard.restores == [("old", 11)]


def test_delivery_copies_result_when_target_changed() -> None:
    clipboard = FakeClipboard()
    service = DeliveryService(FakeTargetManager(valid=False), clipboard, FakeKeyboard())
    result = service.deliver(TARGET, "新的文字")
    assert not result.inserted
    assert "目标已变化" in result.reason
    assert clipboard.restores == []
    assert clipboard.copied == ["新的文字"]


def test_delivery_types_result_when_original_clipboard_cannot_be_preserved() -> None:
    clipboard = FakeClipboard(snapshot=None)
    keyboard = FakeKeyboard()
    service = DeliveryService(FakeTargetManager(), clipboard, keyboard)
    result = service.deliver(TARGET, "新的文字")
    assert result.inserted
    assert keyboard.typed == ["新的文字"]
    assert clipboard.copied == []


def test_delivery_pastes_result_when_unicode_fallback_is_rejected() -> None:
    clipboard = FakeClipboard(snapshot=None)
    keyboard = FakeKeyboard(unicode_inserted=False)
    service = DeliveryService(FakeTargetManager(), clipboard, keyboard)
    result = service.deliver(TARGET, "新的文字")
    assert result.inserted
    assert keyboard.typed == ["新的文字"]
    assert keyboard.paste_calls == 1
    assert clipboard.copied == ["新的文字"]


def test_delivery_keeps_result_copied_when_unicode_and_paste_are_rejected() -> None:
    clipboard = FakeClipboard(snapshot=None)
    keyboard = FakeKeyboard(pasted=False, unicode_inserted=False)
    service = DeliveryService(FakeTargetManager(), clipboard, keyboard)
    result = service.deliver(TARGET, "新的文字")
    assert not result.inserted
    assert keyboard.typed == ["新的文字"]
    assert keyboard.paste_calls == 1
    assert clipboard.copied == ["新的文字"]
