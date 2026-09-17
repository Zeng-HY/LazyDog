from __future__ import annotations

import sys
from dataclasses import replace
from typing import Callable

import sounddevice as sd
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QKeySequenceEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from voiceanywhere.config import SettingsStore, format_terms, parse_terms
from voiceanywhere.models import AppSettings, LatestResult, SessionState, VoiceMode
from voiceanywhere.services import OpenRouterClient
from voiceanywhere.session import VoiceSessionController
from voiceanywhere.storage import LocalStore
from voiceanywhere.windows import (
    Clipboard,
    DeliveryService,
    InputActivityMonitor,
    KeyboardInjector,
    NativeHotkeyFilter,
    TargetManager,
    parse_hotkey,
)


class StatusBar(QWidget):
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.label = QLabel()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_requested)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.addWidget(self.label)
        layout.addWidget(self.cancel_button)
        self.setStyleSheet(
            "StatusBar { background: #202124; color: white; border-radius: 8px; }"
            "QLabel { color: white; } QPushButton { color: white; padding: 2px 8px; }"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(self, message: str, cancellable: bool = False, timeout_ms: int | None = None) -> None:
        self.label.setText(message)
        self.cancel_button.setVisible(cancellable)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            self.move(rect.center().x() - self.width() // 2, rect.bottom() - self.height() - 48)
        self.show()
        if timeout_ms:
            self._hide_timer.start(timeout_ms)
        else:
            self._hide_timer.stop()


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, has_key: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VoiceAnywhere 设置")
        self._initial_settings = settings
        self._clear_key = False
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.microphone = QComboBox()
        self.microphone.addItem("系统默认麦克风", None)
        try:
            devices = sd.query_devices()
            for index, device in enumerate(devices):
                if device["max_input_channels"] > 0:
                    self.microphone.addItem(f"{index}: {device['name']}", index)
        except Exception:
            pass
        position = self.microphone.findData(settings.microphone)
        self.microphone.setCurrentIndex(position if position >= 0 else 0)
        form.addRow("麦克风", self.microphone)

        self.hotkey = QKeySequenceEdit(QKeySequence(settings.hotkey))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setClearButtonEnabled(True)
        self.hotkey.setToolTip("单击后一次按下组合键，例如 Ctrl+Alt+Space")
        form.addRow("开始/结束快捷键", self.hotkey)
        hotkey_help = QLabel("单击框后直接按组合键；至少包含 Ctrl、Alt 或 Shift 与一个主按键。")
        hotkey_help.setWordWrap(True)
        form.addRow("", hotkey_help)

        self.mode = QComboBox()
        self.mode.addItem("忠实整理", VoiceMode.FAITHFUL)
        self.mode.addItem("仅转写", VoiceMode.TRANSCRIBE_ONLY)
        self.mode.setCurrentIndex(0 if settings.mode == VoiceMode.FAITHFUL else 1)
        form.addRow("默认模式", self.mode)

        self.language = QComboBox()
        self.language.addItem("跟随口述", "follow")
        self.language.addItem("中文", "zh")
        self.language.addItem("英文", "en")
        self.language.setCurrentIndex(max(0, self.language.findData(settings.output_language)))
        form.addRow("默认输出语言", self.language)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("已保存（留空不修改）" if has_key else "粘贴 OpenRouter API Key")
        form.addRow("OpenRouter API Key", self.api_key)
        self.key_status = QLabel("当前状态：已保存" if has_key else "当前状态：未保存")
        form.addRow("本机凭据", self.key_status)
        layout.addLayout(form)

        consent = QLabel(
            "录音会发送到 OpenRouter 识别服务；转写、词条和本次输出设置会发送到整理服务。"
            "P0 不读取附近文字。API Key 使用当前 Windows 用户的 DPAPI 本地加密。"
        )
        consent.setWordWrap(True)
        layout.addWidget(consent)

        layout.addWidget(QLabel("词条：每行“标准写法 | 别名1,别名2 | global/chat/email/neutral”"))
        self.terms = QPlainTextEdit(format_terms(settings.terms))
        self.terms.setPlaceholderText("Unimed | 尤尼迈德 | global\n510(k) | 五幺零K | global")
        self.terms.setMinimumHeight(150)
        layout.addWidget(self.terms)

        self.clear_key = QCheckBox("清除已保存的 API Key")
        self.clear_key.setEnabled(has_key)
        layout.addWidget(self.clear_key)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[AppSettings, str | None, bool]:
        hotkey = self.hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        parse_hotkey(hotkey)
        settings = AppSettings(
            microphone=self.microphone.currentData(),
            hotkey=hotkey,
            mode=self.mode.currentData(),
            output_language=self.language.currentData(),
            terms=parse_terms(self.terms.toPlainText()),
        )
        key = self.api_key.text().strip() or None
        return settings, key, self.clear_key.isChecked()


class RecentResultDialog(QDialog):
    def __init__(
        self,
        result: LatestResult,
        save_case: Callable[[LatestResult, str, str], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result = result
        self._save_case = save_case
        self.setWindowTitle("最近一次结果")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("原转写"))
        transcript = QPlainTextEdit(result.transcript)
        transcript.setReadOnly(True)
        transcript.setMaximumHeight(140)
        layout.addWidget(transcript)
        layout.addWidget(QLabel("整理结果（可编辑后复制）"))
        self.text = QPlainTextEdit(result.result_text)
        layout.addWidget(self.text)
        if result.attention or result.issue:
            attention = QLabel("\n".join((*result.attention, result.issue)))
            attention.setWordWrap(True)
            layout.addWidget(attention)
        layout.addWidget(QLabel("问题说明（仅在保存问题案例时写入本地）"))
        self.issue = QLineEdit()
        layout.addWidget(self.issue)
        buttons = QHBoxLayout()
        copy = QPushButton("复制结果")
        copy.clicked.connect(self.copy_result)
        save = QPushButton("保存问题案例")
        save.clicked.connect(self.save_case)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        buttons.addWidget(copy)
        buttons.addWidget(save)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def copy_result(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())

    def save_case(self) -> None:
        try:
            path = self._save_case(self.result, self.text.toPlainText(), self.issue.text().strip())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "无法保存", str(exc))
            return
        QMessageBox.information(self, "已保存", f"问题案例已保存到：\n{path}")


class VoiceAnywhereApp:
    def __init__(self, application: QApplication) -> None:
        self.application = application
        self.settings_store = SettingsStore()
        self.local_store = LocalStore()
        self.settings = self.settings_store.load()
        self.hotkeys = NativeHotkeyFilter()
        self.application.installNativeEventFilter(self.hotkeys)
        self.hotkeys.triggered.connect(self._on_hotkey)

        self.activity = InputActivityMonitor()
        activity_monitor_available = self.activity.install()
        self.controller = VoiceSessionController(
            settings_provider=lambda: self.settings,
            api_key_provider=lambda: self.settings_store.secrets.get("openrouter_api_key"),
            target_manager=TargetManager(),
            activity_monitor=self.activity,
            delivery_service=DeliveryService(TargetManager(), Clipboard(), KeyboardInjector()),
            service_client=OpenRouterClient(),
            local_store=self.local_store,
        )
        self.controller.status_changed.connect(self._show_status)
        self.controller.state_changed.connect(self._on_state_change)
        self.controller.latest_changed.connect(lambda _result: self._sync_menu())

        self.status = StatusBar()
        self.status.cancel_requested.connect(lambda: self.controller.cancel())
        self.tray = QSystemTrayIcon(application.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), application)
        self.menu = QMenu()
        self.toggle_action = QAction("开始语音输入", self.menu)
        self.toggle_action.triggered.connect(self.controller.toggle)
        self.mode_action = QAction("仅转写", self.menu)
        self.mode_action.setCheckable(True)
        self.mode_action.setChecked(self.settings.mode == VoiceMode.TRANSCRIBE_ONLY)
        self.mode_action.triggered.connect(self._toggle_mode)
        self.recent_action = QAction("最近一次结果", self.menu)
        self.recent_action.triggered.connect(self.show_recent)
        self.settings_action = QAction("设置", self.menu)
        self.settings_action.triggered.connect(self.show_settings)
        quit_action = QAction("退出", self.menu)
        quit_action.triggered.connect(application.quit)
        self.menu.addAction(self.toggle_action)
        self.menu.addAction(self.mode_action)
        self.menu.addSeparator()
        self.menu.addAction(self.recent_action)
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._sync_menu()
        try:
            self.hotkeys.register_main(self.settings.hotkey)
        except (ValueError, RuntimeError) as exc:
            self._show_status(f"默认快捷键不可用：{exc}")
        if not activity_monitor_available:
            self._show_status("无法监测会话期间的输入操作；结果将只保留，不会自动插入")
        self.application.aboutToQuit.connect(self.shutdown)

    def _on_hotkey(self, kind: str) -> None:
        if kind == "main":
            self.controller.toggle()
        elif kind == "cancel":
            self.controller.cancel()

    def _on_state_change(self, state: SessionState) -> None:
        if state == SessionState.IDLE:
            self.hotkeys.unregister_cancel()
        else:
            self.hotkeys.register_cancel()
        self._sync_menu()

    def _sync_menu(self) -> None:
        state = self.controller.state
        self.toggle_action.setText("结束录音" if state == SessionState.RECORDING else "开始语音输入")
        self.recent_action.setEnabled(self.controller.latest is not None)
        self.mode_action.setChecked(self.settings.mode == VoiceMode.TRANSCRIBE_ONLY)

    def _show_status(self, message: str) -> None:
        cancellable = self.controller.state == SessionState.PROCESSING
        timeout = 1800 if message == "已插入" else (5000 if self.controller.state == SessionState.IDLE else None)
        self.status.show_message(message, cancellable, timeout)

    def _toggle_mode(self) -> None:
        if self.controller.state != SessionState.IDLE:
            self._show_status("请在当前会话结束后再切换模式")
            self._sync_menu()
            return
        mode = VoiceMode.TRANSCRIBE_ONLY if self.mode_action.isChecked() else VoiceMode.FAITHFUL
        self.settings = replace(self.settings, mode=mode)
        self.settings_store.save(self.settings)
        self._sync_menu()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_recent()

    def show_settings(self) -> None:
        if self.controller.state != SessionState.IDLE:
            self._show_status("请在当前会话结束后再修改设置")
            return
        dialog = SettingsDialog(
            self.settings,
            bool(self.settings_store.secrets.get("openrouter_api_key")),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_settings, key, clear_key = dialog.values()
            # A successful dialog close is not enough: confirm that DPAPI can read the value
            # before claiming the API key was saved.
            if clear_key:
                self.settings_store.secrets.delete("openrouter_api_key")
                if self.settings_store.secrets.get("openrouter_api_key"):
                    raise RuntimeError("API Key 未能从本机凭据存储中清除")
            elif key:
                self.settings_store.secrets.set("openrouter_api_key", key)
                if self.settings_store.secrets.get("openrouter_api_key") != key:
                    raise RuntimeError("API Key 未能写入或读取本机凭据存储")
            hotkey_changed = new_settings.hotkey != self.settings.hotkey
            if hotkey_changed:
                self.hotkeys.replace_main(new_settings.hotkey)
            self.settings_store.save(new_settings)
            persisted = self.settings_store.load()
            if persisted.hotkey != new_settings.hotkey:
                raise RuntimeError("快捷键未能写入本机设置文件")
            self.settings = new_settings
            self._sync_menu()
            state = "已保存 API Key" if key else ("已清除 API Key" if clear_key else "设置已保存")
            self._show_status(state)
        except Exception as exc:
            if "hotkey_changed" in locals() and hotkey_changed:
                try:
                    self.hotkeys.replace_main(self.settings.hotkey)
                except Exception:
                    pass
            QMessageBox.warning(dialog, "无法保存设置", str(exc))

    def show_recent(self) -> None:
        if not self.controller.latest:
            self._show_status("当前没有可查看的结果")
            return
        RecentResultDialog(self.controller.latest, self.local_store.save_case).exec()

    def shutdown(self) -> None:
        self.hotkeys.unregister_main()
        self.hotkeys.unregister_cancel()
        self.application.removeNativeEventFilter(self.hotkeys)
        self.activity.uninstall()
        self.controller.shutdown()


def main() -> int:
    application = QApplication(sys.argv)
    application.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "VoiceAnywhere", "此 Windows 会话没有可用的系统托盘。")
        return 1
    VoiceAnywhereApp(application)
    return application.exec()
