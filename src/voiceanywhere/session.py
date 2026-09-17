from __future__ import annotations

import concurrent.futures
import time
import uuid
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from voiceanywhere.audio import AudioCapture, BatchAsrSession, MAX_SECONDS
from voiceanywhere.models import (
    AppSettings,
    ComposeInput,
    ComposeResult,
    LatestResult,
    SessionState,
    VoiceMode,
)
from voiceanywhere.services import OpenRouterClient, ServiceError
from voiceanywhere.storage import LocalStore
from voiceanywhere.windows import DeliveryService, TargetManager


PROCESSING_TIMEOUT_SECONDS = 30.0
SLOW_PROCESSING_SECONDS = 4.0


@dataclass(frozen=True)
class WorkerPacket:
    token: str
    transcript: str
    composed: ComposeResult | None
    asr_ms: int | None
    compose_ms: int | None
    error: str = ""


class VoiceSessionController(QObject):
    status_changed = Signal(str)
    state_changed = Signal(object)
    latest_changed = Signal(object)
    worker_completed = Signal(object)

    def __init__(
        self,
        settings_provider: Callable[[], AppSettings],
        api_key_provider: Callable[[], str | None],
        target_manager: TargetManager,
        delivery_service: DeliveryService,
        service_client: OpenRouterClient,
        local_store: LocalStore,
    ) -> None:
        super().__init__()
        self._settings_provider = settings_provider
        self._api_key_provider = api_key_provider
        self.target_manager = target_manager
        self.delivery_service = delivery_service
        self.service_client = service_client
        self.local_store = local_store
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="voiceanywhere")
        self._state = SessionState.IDLE
        self._token: str | None = None
        self._target = None
        self._asr: BatchAsrSession | None = None
        self._api_key = ""
        self._deadline = 0.0
        self.latest: LatestResult | None = None
        self.worker_completed.connect(self._on_worker_completed)

    @property
    def state(self) -> SessionState:
        return self._state

    def toggle(self) -> None:
        if self._state == SessionState.IDLE:
            self.start()
        elif self._state == SessionState.RECORDING:
            self.stop()
        else:
            self.cancel("已取消上一会话并开始新的录音")
            self.start()

    def start(self) -> bool:
        api_key = self._api_key_provider() or ""
        if not api_key:
            self.status_changed.emit("请先在设置中保存 OpenRouter API Key")
            return False
        try:
            target = self.target_manager.capture()
        except Exception as exc:
            self.status_changed.emit(f"无法确认输入目标：{exc}")
            return False
        if target.is_password:
            self.status_changed.emit("密码或受保护输入框不支持语音直写")
            return False
        settings = self._settings_provider()
        capture = AudioCapture(settings.microphone)
        asr = BatchAsrSession(self.service_client, capture)
        try:
            asr.start()
        except Exception as exc:
            self.status_changed.emit(f"无法开始录音：{exc}")
            return False
        self._token = uuid.uuid4().hex
        self._target = target
        self._asr = asr
        self._api_key = api_key
        self.latest = LatestResult(session_id=self._token, app_style=target.app_style)
        self._set_state(SessionState.RECORDING)
        self.status_changed.emit("正在听")
        QTimer.singleShot(MAX_SECONDS * 1000, lambda: self._on_maximum_duration(self._token))
        return True

    def stop(self) -> None:
        if self._state != SessionState.RECORDING or self._asr is None or self.latest is None:
            return
        token = self._token
        try:
            wav_bytes = self._asr.stop_capture()
        except Exception as exc:
            self._finish_without_delivery(f"无法停止录音：{exc}")
            return
        if self._asr.capture.is_silent():
            self.latest.audio_wav = None
            self._finish_without_delivery("没有听到可用语音")
            return
        self.latest.audio_wav = wav_bytes
        self.latest.stopped_at_monotonic = time.monotonic()
        self._deadline = self.latest.stopped_at_monotonic + PROCESSING_TIMEOUT_SECONDS
        self._set_state(SessionState.PROCESSING)
        self.status_changed.emit("正在识别")
        QTimer.singleShot(int(SLOW_PROCESSING_SECONDS * 1000), lambda: self._on_slow_processing(token))
        settings = self._settings_provider()
        self._executor.submit(
            self._run_worker, token, wav_bytes, settings, self._api_key, self._deadline, self._target.app_style
        )

    def cancel(self, message: str = "已取消") -> None:
        if self._state == SessionState.IDLE:
            return
        token = self._token
        self._token = None
        if self._asr is not None:
            self._asr.cancel()
        self._set_state(SessionState.IDLE)
        if self.latest and self.latest.session_id == token:
            self.latest.issue = message
            self.latest_changed.emit(self.latest)
        self.status_changed.emit(message)

    def shutdown(self) -> None:
        self.cancel("程序已退出")
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.service_client.close()

    def _run_worker(
        self,
        token: str | None,
        wav_bytes: bytes,
        settings: AppSettings,
        api_key: str,
        deadline: float,
        app_style: str,
    ) -> None:
        if token is None:
            return
        transcript = ""
        asr_ms: int | None = None
        compose_ms: int | None = None
        try:
            started = time.monotonic()
            transcript_result = self.service_client.transcribe(
                wav_bytes, api_key, max(0.5, deadline - time.monotonic())
            )
            asr_ms = int((time.monotonic() - started) * 1000)
            transcript = transcript_result.text
            if settings.mode == VoiceMode.TRANSCRIBE_ONLY:
                composed = ComposeResult(transcript)
            else:
                started = time.monotonic()
                source = ComposeInput(
                    transcript=transcript,
                    output_language=settings.output_language,
                    app_style=app_style,
                    nearby_text="",
                    confirmed_terms=tuple(settings.terms),
                )
                composed = self.service_client.compose(
                    source, api_key, max(0.5, deadline - time.monotonic())
                )
                compose_ms = int((time.monotonic() - started) * 1000)
            self.worker_completed.emit(WorkerPacket(token, transcript, composed, asr_ms, compose_ms))
        except (ServiceError, RuntimeError) as exc:
            self.worker_completed.emit(WorkerPacket(token, transcript, None, asr_ms, compose_ms, str(exc)))
        except Exception as exc:  # Last-resort failure boundary; raw service data never reaches the UI.
            self.worker_completed.emit(WorkerPacket(token, transcript, None, asr_ms, compose_ms, f"处理失败：{exc}"))

    def _on_worker_completed(self, packet: WorkerPacket) -> None:
        if packet.token != self._token or self.latest is None:
            return
        self.latest.transcript = packet.transcript
        self.latest.timings_ms["stop_to_asr_final"] = packet.asr_ms
        self.latest.timings_ms["compose"] = packet.compose_ms
        if self.latest.stopped_at_monotonic is not None:
            self.latest.timings_ms["stop_to_insert"] = int(
                (time.monotonic() - self.latest.stopped_at_monotonic) * 1000
            )
        if packet.error or packet.composed is None:
            if packet.transcript and self.delivery_service.copy_to_clipboard(packet.transcript):
                self.latest.result_text = packet.transcript
                self._finish_without_delivery(f"{packet.error or '整理未完成'}；原转写已复制，可直接粘贴")
                return
            self._finish_without_delivery(packet.error or "整理未完成，可查看原转写")
            return
        self.latest.result_text = packet.composed.text
        self.latest.attention = packet.composed.attention
        delivery = self.delivery_service.deliver(self._target, packet.composed.text)
        if delivery.inserted:
            self._finish("已插入", True)
        else:
            self._finish_without_delivery(delivery.reason)

    def _on_slow_processing(self, token: str | None) -> None:
        if token != self._token or self._state != SessionState.PROCESSING:
            return
        self.status_changed.emit("仍在处理；完成后会直接插入或复制结果")

    def _on_maximum_duration(self, token: str | None) -> None:
        if token == self._token and self._state == SessionState.RECORDING:
            self.status_changed.emit("已达到120秒上限，正在处理已录内容")
            self.stop()

    def _finish_without_delivery(self, reason: str) -> None:
        self._finish(reason, False)

    def _finish(self, message: str, inserted: bool) -> None:
        if self.latest:
            self.latest.issue = "" if inserted else message
            self.latest_changed.emit(self.latest)
            self.local_store.append_metric(self.latest, message, inserted)
        self._asr = None
        self._target = None
        self._api_key = ""
        self._token = None
        self._set_state(SessionState.IDLE)
        self.status_changed.emit(message)

    def _set_state(self, state: SessionState) -> None:
        self._state = state
        self.state_changed.emit(state)
