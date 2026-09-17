from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class SessionState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class VoiceMode(str, Enum):
    FAITHFUL = "faithful"
    TRANSCRIBE_ONLY = "transcribe_only"


OutputLanguage = Literal["follow", "zh", "en"]


@dataclass(frozen=True)
class TermEntry:
    canonical: str
    aliases: tuple[str, ...] = ()
    scope: str = "global"

    def applies_to(self, app_style: str) -> bool:
        return self.scope in {"global", app_style}


@dataclass
class AppSettings:
    microphone: int | None = None
    hotkey: str = "Ctrl+Alt+Space"
    mode: VoiceMode = VoiceMode.FAITHFUL
    output_language: OutputLanguage = "follow"
    terms: list[TermEntry] = field(default_factory=list)


@dataclass(frozen=True)
class TargetSnapshot:
    foreground_hwnd: int
    process_id: int
    focus_hwnd: int = 0
    focus_class: str = ""
    is_password: bool = False
    app_style: str = "neutral"


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    duration_seconds: float
    usage: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComposeInput:
    transcript: str
    output_language: OutputLanguage
    app_style: str
    nearby_text: str
    confirmed_terms: tuple[TermEntry, ...]


@dataclass(frozen=True)
class ComposeResult:
    text: str
    attention: tuple[str, ...] = ()
    usage: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    inserted: bool
    reason: str = ""


@dataclass
class LatestResult:
    session_id: str
    transcript: str = ""
    result_text: str = ""
    attention: tuple[str, ...] = ()
    audio_wav: bytes | None = None
    app_style: str = "neutral"
    stopped_at_monotonic: float | None = None
    timings_ms: dict[str, int | None] = field(default_factory=dict)
    issue: str = ""
