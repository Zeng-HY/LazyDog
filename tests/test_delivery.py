from voiceanywhere.models import TargetSnapshot
from voiceanywhere.windows import DeliveryService


class FakeTargetManager:
    def __init__(self, valid: bool = True, unicode_ok: bool = False) -> None:
        self.valid = valid
        self.unicode_ok = unicode_ok

    def is_still_target(self, _target) -> bool:
        return self.valid

    def allows_unicode_fallback(self, _target, _text: str) -> bool:
        return self.unicode_ok


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

    def paste(self) -> bool:
        return self.pasted

    def unicode_text(self, _text: str) -> bool:
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


def test_delivery_copies_result_when_original_clipboard_cannot_be_preserved() -> None:
    clipboard = FakeClipboard(snapshot=None)
    service = DeliveryService(FakeTargetManager(unicode_ok=False), clipboard, FakeKeyboard())
    result = service.deliver(TARGET, "新的文字")
    assert not result.inserted
    assert "剪贴板" in result.reason
    assert clipboard.copied == ["新的文字"]
