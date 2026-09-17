from __future__ import annotations

import audioop
import io
import threading
import wave

import sounddevice as sd

from voiceanywhere.models import TranscriptResult
from voiceanywhere.services import OpenRouterClient


SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2
MAX_SECONDS = 120
SILENCE_RMS_THRESHOLD = 120


class AudioCapture:
    """P0 capture: audio stays in memory until the active session completes."""

    def __init__(self, device: int | None = None) -> None:
        self.device = device
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._started = False

    def start(self) -> None:
        if self._started:
            raise RuntimeError("录音已经开始")
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=self.device,
            callback=self._on_audio,
        )
        self._stream.start()
        self._started = True

    def stop(self) -> bytes:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._stream = None
        self._started = False
        return self.wav_bytes()

    def cancel(self) -> None:
        if self._stream is not None:
            self._stream.abort()
            self._stream.close()
        self._stream = None
        self._started = False
        with self._lock:
            self._chunks = []

    def push(self, audio_chunk: bytes) -> None:
        with self._lock:
            self._chunks.append(audio_chunk)

    def raw_pcm(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)

    def duration_seconds(self) -> float:
        return len(self.raw_pcm()) / (SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)

    def is_silent(self) -> bool:
        raw = self.raw_pcm()
        return not raw or audioop.rms(raw, SAMPLE_WIDTH) < SILENCE_RMS_THRESHOLD

    def wav_bytes(self) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(SAMPLE_WIDTH)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(self.raw_pcm())
        return output.getvalue()

    def _on_audio(self, indata, _frames, _time, status) -> None:
        if status:
            # The next stages use the complete buffer. Audio callback status is not treated as text evidence.
            return
        self.push(indata.tobytes())


class BatchAsrSession:
    """Interface-compatible P0 ASR session; P1 can stream in push without changing callers."""

    def __init__(self, client: OpenRouterClient, capture: AudioCapture) -> None:
        self.client = client
        self.capture = capture
        self._cancelled = False
        self._wav_bytes: bytes | None = None

    def start(self) -> None:
        self.capture.start()

    def push(self, audio_chunk: bytes) -> None:
        self.capture.push(audio_chunk)

    def finish(self, api_key: str, timeout_seconds: float) -> tuple[TranscriptResult, bytes]:
        if self._cancelled:
            raise RuntimeError("会话已经取消")
        wav_bytes = self._wav_bytes or self.capture.stop()
        self._wav_bytes = wav_bytes
        return self.client.transcribe(wav_bytes, api_key, timeout_seconds), wav_bytes

    def stop_capture(self) -> bytes:
        self._wav_bytes = self.capture.stop()
        return self._wav_bytes

    def cancel(self) -> None:
        self._cancelled = True
        self.capture.cancel()
