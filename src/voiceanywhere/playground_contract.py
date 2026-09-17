from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from voiceanywhere.models import TermEntry


EDIT_LEVELS = ("minimal", "light", "auto")
FILLER_POLICIES = ("remove_meaningless", "preserve")
TONES = ("preserve", "conversational", "formal", "polite")
LAYOUTS = ("preserve", "paragraphs", "list", "auto")
PUNCTUATIONS = ("standard", "minimal")
NUMBER_STYLES = ("normalize_unambiguous", "preserve")
APP_STYLES = ("neutral", "chat", "email")
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class PlaygroundSettings:
    edit_level: str = "minimal"
    filler_policy: str = "remove_meaningless"
    output_language: str = "preserve"
    tone: str = "preserve"
    layout: str = "preserve"
    punctuation: str = "standard"
    number_style: str = "normalize_unambiguous"
    app_style: str = "neutral"

    def validate(self) -> None:
        _validate_member("edit_level", self.edit_level, EDIT_LEVELS)
        _validate_member("filler_policy", self.filler_policy, FILLER_POLICIES)
        if not self.output_language.strip():
            raise ValueError("output_language 不能为空")
        _validate_member("tone", self.tone, TONES)
        _validate_member("layout", self.layout, LAYOUTS)
        _validate_member("punctuation", self.punctuation, PUNCTUATIONS)
        _validate_member("number_style", self.number_style, NUMBER_STYLES)
        _validate_member("app_style", self.app_style, APP_STYLES)

    def as_request_settings(self) -> dict[str, str]:
        self.validate()
        payload = asdict(self)
        return {key: str(value) for key, value in payload.items()}


@dataclass(frozen=True)
class PlaygroundParameters:
    model: str
    system_prompt: str
    reasoning_effort: str = "low"
    max_tokens: int = 4096
    settings: PlaygroundSettings = field(default_factory=PlaygroundSettings)

    def validate(self) -> None:
        if not self.model.strip():
            raise ValueError("模型名称不能为空")
        if not self.system_prompt.strip():
            raise ValueError("系统提示词不能为空")
        _validate_member("推理强度", self.reasoning_effort, REASONING_EFFORTS)
        if not 128 <= self.max_tokens <= 4096:
            raise ValueError("最大输出 tokens 必须在 128 到 4096 之间")
        self.settings.validate()

    def as_preset(self) -> dict[str, Any]:
        self.validate()
        return {
            "model": self.model,
            "system_prompt": self.system_prompt,
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": self.max_tokens,
            "settings": self.settings.as_request_settings(),
        }

    @classmethod
    def from_preset(cls, value: dict[str, Any]) -> PlaygroundParameters:
        settings = value.get("settings")
        if not isinstance(settings, dict):
            raise ValueError("预设缺少 settings")
        return cls(
            model=_required_string(value, "model"),
            system_prompt=_required_string(value, "system_prompt"),
            reasoning_effort=_required_string(value, "reasoning_effort"),
            max_tokens=_required_int(value, "max_tokens"),
            settings=PlaygroundSettings(
                edit_level=_required_string(settings, "edit_level"),
                filler_policy=_required_string(settings, "filler_policy"),
                output_language=_required_string(settings, "output_language"),
                tone=_required_string(settings, "tone"),
                layout=_required_string(settings, "layout"),
                punctuation=_required_string(settings, "punctuation"),
                number_style=_required_string(settings, "number_style"),
                app_style=_required_string(settings, "app_style"),
            ),
        )


@dataclass(frozen=True)
class PlaygroundTerm:
    spoken: str
    written: str

    def as_request_value(self) -> dict[str, str]:
        return {"spoken": self.spoken, "written": self.written}


@dataclass(frozen=True)
class PlaygroundInput:
    transcript: str
    nearby_text: str
    confirmed_terms: tuple[PlaygroundTerm, ...]
    settings: PlaygroundSettings

    def as_request_payload(self) -> dict[str, Any]:
        return {
            "transcript": self.transcript,
            "nearby_text": self.nearby_text,
            "confirmed_terms": [term.as_request_value() for term in self.confirmed_terms],
            "settings": self.settings.as_request_settings(),
        }


@dataclass(frozen=True)
class PlaygroundAttention:
    span: str
    issue: str


@dataclass(frozen=True)
class PlaygroundResult:
    text: str
    attention: tuple[PlaygroundAttention, ...] = ()
    usage: dict[str, object] = field(default_factory=dict)


def terms_for_playground(terms: tuple[TermEntry, ...], app_style: str) -> tuple[PlaygroundTerm, ...]:
    """Map the existing local alias list to the strict v2 spoken/written contract."""
    mapped: list[PlaygroundTerm] = []
    seen: set[tuple[str, str]] = set()
    for term in terms:
        if not term.applies_to(app_style):
            continue
        for alias in term.aliases:
            item = (alias, term.canonical)
            if alias and item not in seen:
                mapped.append(PlaygroundTerm(*item))
                seen.add(item)
    return tuple(mapped)


def _validate_member(label: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{label} 必须是以下之一：{', '.join(allowed)}")


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"预设字段 {key} 无效")
    return item


def _required_int(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"预设字段 {key} 无效")
    return item
