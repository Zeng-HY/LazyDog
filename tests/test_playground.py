from PySide6.QtWidgets import QApplication

from pathlib import Path

from voiceanywhere.playground import AUTO_DEFAULT_PARAMETERS, TextPlaygroundWindow
from voiceanywhere.services import AUTO_DEFAULT_SYSTEM_PROMPT


def test_playground_is_text_only_and_starts_with_a_clear_status() -> None:
    app = QApplication.instance() or QApplication([])
    window = TextPlaygroundWindow()
    assert "自动整理试验台" in window.windowTitle()
    assert window.source.toPlainText() == ""
    assert window.output.toPlainText() == ""
    assert window.status.text() == "等待输入"
    assert AUTO_DEFAULT_PARAMETERS.model == "openai/gpt-5.6-luna"
    assert AUTO_DEFAULT_PARAMETERS.reasoning_effort == "low"
    assert AUTO_DEFAULT_PARAMETERS.max_tokens == 2048
    assert AUTO_DEFAULT_PARAMETERS.settings.edit_level == "auto"
    assert AUTO_DEFAULT_PARAMETERS.settings.layout == "auto"
    assert window._automatic_parameters().settings.output_language == "preserve"
    shared_policy = Path(__file__).parents[1] / "shared" / "auto_default_policy_v1.txt"
    assert AUTO_DEFAULT_SYSTEM_PROMPT == shared_policy.read_text(encoding="utf-8").strip()
    window.close()
    _ = app
