from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from voiceanywhere.app import SettingsDialog
from voiceanywhere.models import AppSettings


def test_settings_dialog_save_button_accepts_and_returns_typed_key() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_key=False)
    dialog.api_key.setText("test-key")
    button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save)
    assert button is not None
    button.click()
    assert dialog.result() == dialog.DialogCode.Accepted
    _, key, clear_key = dialog.values()
    assert key == "test-key"
    assert clear_key is False
    dialog.deleteLater()
    _ = app


def test_settings_dialog_captures_a_single_hotkey_chord_as_portable_text() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_key=False)
    dialog.hotkey.setKeySequence(QKeySequence("Ctrl+Alt+F8"))
    settings, _, _ = dialog.values()
    assert settings.hotkey == "Ctrl+Alt+F8"
    assert dialog.hotkey.maximumSequenceLength() == 1
    dialog.deleteLater()
    _ = app
