from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from dataclasses import dataclass, replace

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from voiceanywhere.config import SettingsStore
from voiceanywhere.playground_contract import (
    PlaygroundInput,
    PlaygroundParameters,
    PlaygroundResult,
    PlaygroundSettings,
    terms_for_playground,
)
from voiceanywhere.services import AUTO_DEFAULT_SYSTEM_PROMPT, COMPOSE_MODEL, OpenRouterClient, ServiceError


AUTO_DEFAULT_PARAMETERS = PlaygroundParameters(
    model=COMPOSE_MODEL,
    system_prompt=AUTO_DEFAULT_SYSTEM_PROMPT,
    reasoning_effort="low",
    max_tokens=2048,
    settings=PlaygroundSettings(edit_level="auto", layout="auto"),
)


@dataclass(frozen=True)
class WorkerResult:
    result: PlaygroundResult | None
    elapsed_ms: int
    error: str = ""


class TextPlaygroundWindow(QWidget):
    """Single-run public-behavior test surface. Advanced policy parameters stay internal."""

    completed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.settings_store = SettingsStore()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="voiceanywhere-playground")
        self._running = False
        self._started_at: float | None = None
        self.setWindowTitle("VoiceAnywhere 自动整理试验台")
        self.resize(1050, 710)
        self._build_ui()
        self.completed.connect(self._on_completed)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(50)
        self.elapsed_timer.timeout.connect(self._refresh_elapsed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("自动整理试验台")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        note = QLabel(
            "粘贴模拟口述后直接运行。系统会逐处判断是否需要去除无意义填充音、处理明确改口、"
            "补标点、分段或分点；不要求你选择润色力度。不会录音、插入其他程序或保存正文。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        controls = QFormLayout()
        controls.addRow("内部策略", QLabel("自动默认策略 · 最小必要整理 · 忠实保真"))
        controls.addRow("模型", QLabel(COMPOSE_MODEL))
        self.output_language = QComboBox()
        self.output_language.addItem("保持原语言", "preserve")
        self.output_language.addItem("中文", "zh")
        self.output_language.addItem("英文", "en")
        controls.addRow("输出语言", self.output_language)
        self.app_style = QComboBox()
        self.app_style.addItem("通用文本", "neutral")
        self.app_style.addItem("聊天", "chat")
        self.app_style.addItem("邮件正文", "email")
        controls.addRow("输入场景", self.app_style)
        self.credential_status = QLabel()
        controls.addRow("OpenRouter API Key", self.credential_status)
        layout.addLayout(controls)

        key_row = QHBoxLayout()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("未保存时，在此粘贴并保存；已保存则留空")
        save_key = QPushButton("保存 API Key")
        save_key.clicked.connect(self._save_api_key)
        key_row.addWidget(self.api_key, 1)
        key_row.addWidget(save_key)
        layout.addLayout(key_row)
        self._refresh_credential_status()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(QLabel("模拟口述"))
        self.source = QPlainTextEdit()
        self.source.setPlaceholderText(
            "例如：哎呀，我最近好多活都没有做。机票和专家回信这个事情，"
            "我要先确认航班再买票，然后给专家回信。报表还要领导审核之前，审核之后……"
        )
        input_layout.addWidget(self.source)
        input_layout.addWidget(QLabel("附近文字（可选，仅作弱衔接提示）"))
        self.nearby_text = QPlainTextEdit()
        self.nearby_text.setMaximumHeight(80)
        input_layout.addWidget(self.nearby_text)
        splitter.addWidget(input_panel)

        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(QLabel("自动整理结果"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        output_layout.addWidget(self.output)
        output_layout.addWidget(QLabel("需确认的具体疑点"))
        self.attention = QPlainTextEdit()
        self.attention.setReadOnly(True)
        self.attention.setMaximumHeight(120)
        output_layout.addWidget(self.attention)
        splitter.addWidget(output_panel)
        splitter.setSizes([520, 520])
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.run_button = QPushButton("运行自动整理")
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self.run_compose)
        copy_button = QPushButton("复制结果")
        copy_button.clicked.connect(self.copy_result)
        self.status = QLabel("等待输入")
        self.status.setWordWrap(True)
        actions.addWidget(self.run_button)
        actions.addWidget(copy_button)
        actions.addWidget(self.status, 1)
        layout.addLayout(actions)

    def _refresh_credential_status(self) -> None:
        self.credential_status.setText("已保存" if self.settings_store.secrets.get("openrouter_api_key") else "未保存")

    def _save_api_key(self) -> None:
        key = self.api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "未保存", "请输入 OpenRouter API Key。")
            return
        try:
            self.settings_store.secrets.set("openrouter_api_key", key)
            if self.settings_store.secrets.get("openrouter_api_key") != key:
                raise RuntimeError("API Key 未能写入或读取本机凭据存储")
        except Exception as exc:
            QMessageBox.warning(self, "无法保存", str(exc))
            return
        self.api_key.clear()
        self._refresh_credential_status()
        self.status.setText("API Key 已保存")

    def run_compose(self) -> None:
        if self._running:
            return
        transcript = self.source.toPlainText().strip()
        if not transcript:
            self.status.setText("请先粘贴模拟口述内容")
            return
        api_key = self.settings_store.secrets.get("openrouter_api_key")
        if not api_key:
            self.status.setText("请先保存 OpenRouter API Key")
            return
        parameters = self._automatic_parameters()
        settings = self.settings_store.load()
        source = PlaygroundInput(
            transcript=transcript,
            nearby_text=self.nearby_text.toPlainText(),
            confirmed_terms=terms_for_playground(tuple(settings.terms), parameters.settings.app_style),
            settings=parameters.settings,
        )
        self._running = True
        self._started_at = time.perf_counter()
        self.output.clear()
        self.attention.clear()
        self.run_button.setEnabled(False)
        self.status.setText("正在自动整理：0 ms")
        self.elapsed_timer.start()
        self.executor.submit(self._compose_worker, source, parameters, api_key)

    def _automatic_parameters(self) -> PlaygroundParameters:
        settings = replace(
            AUTO_DEFAULT_PARAMETERS.settings,
            output_language=self.output_language.currentData(),
            app_style=self.app_style.currentData(),
        )
        return replace(AUTO_DEFAULT_PARAMETERS, settings=settings)

    def _compose_worker(self, source: PlaygroundInput, parameters: PlaygroundParameters, api_key: str) -> None:
        started = time.perf_counter()
        client = OpenRouterClient()
        try:
            result = client.compose_playground(source, parameters, api_key, timeout_seconds=25.0)
            packet = WorkerResult(result, int((time.perf_counter() - started) * 1000))
        except (ServiceError, RuntimeError, ValueError) as exc:
            packet = WorkerResult(None, int((time.perf_counter() - started) * 1000), str(exc))
        except Exception as exc:
            packet = WorkerResult(None, int((time.perf_counter() - started) * 1000), f"整理失败：{exc}")
        finally:
            client.close()
        self.completed.emit(packet)

    def _on_completed(self, packet: WorkerResult) -> None:
        self.elapsed_timer.stop()
        self._running = False
        self._started_at = None
        self.run_button.setEnabled(True)
        if packet.result is None:
            self.status.setText(f"未完成：{packet.error}（{packet.elapsed_ms} ms）")
            return
        self.output.setPlainText(packet.result.text)
        attention = "\n\n".join(f"{item.span}\n  {item.issue}" for item in packet.result.attention)
        self.attention.setPlainText(attention or "无")
        usage = json.dumps(packet.result.usage, ensure_ascii=False, separators=(",", ":"))
        self.status.setText(f"完成：模型请求 {packet.elapsed_ms} ms；用量 {usage or '{}'}")

    def _refresh_elapsed(self) -> None:
        if self._started_at is not None:
            self.status.setText(f"正在自动整理：{int((time.perf_counter() - self._started_at) * 1000)} ms")

    def copy_result(self) -> None:
        text = self.output.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.status.setText("整理结果已复制")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt interface name
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = TextPlaygroundWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
