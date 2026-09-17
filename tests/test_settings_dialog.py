from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from voiceanywhere.app import SettingsDialog
from voiceanywhere.models import AppSettings, VoiceMode


def test_settings_dialog_save_button_accepts_and_returns_typed_key() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_text_key=False, has_asr_key=False)
    dialog.text_api_key.setText("test-key")
    button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save)
    assert button is not None
    button.click()
    assert dialog.result() == dialog.DialogCode.Accepted
    _, text_key, asr_key, clear_key = dialog.values()
    assert text_key == "test-key"
    assert asr_key is None
    assert clear_key is False
    dialog.deleteLater()
    _ = app


def test_settings_dialog_converts_qt_mode_data_back_to_voice_mode() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_text_key=False, has_asr_key=False)
    dialog.mode.setCurrentIndex(1)
    settings, _, _, _ = dialog.values()
    assert settings.mode == VoiceMode.TRANSCRIBE_ONLY
    dialog.deleteLater()
    _ = app


def test_settings_dialog_captures_a_single_hotkey_chord_as_portable_text() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_text_key=False, has_asr_key=False)
    dialog.hotkey.setKeySequence(QKeySequence("Ctrl+Alt+F8"))
    settings, _, _, _ = dialog.values()
    assert settings.hotkey == "Ctrl+Alt+F8"
    assert dialog.hotkey.maximumSequenceLength() == 1
    dialog.deleteLater()
    _ = app


def test_settings_dialog_prefills_glm_and_deepseek_endpoints() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), has_text_key=False, has_asr_key=False)
    dialog.text_provider.setCurrentIndex(dialog.text_provider.findData("glm"))
    glm, _, _, _ = dialog.values()
    assert glm.providers.text_base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert glm.providers.text_model == "glm-5.2"
    dialog.text_provider.setCurrentIndex(dialog.text_provider.findData("deepseek"))
    deepseek, _, _, _ = dialog.values()
    assert deepseek.providers.text_base_url == "https://api.deepseek.com"
    assert deepseek.providers.text_model == "deepseek-flash"
    dialog.deleteLater()
    _ = app
