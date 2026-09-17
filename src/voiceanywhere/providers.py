from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    base_url: str
    model: str
    supports_transcription: bool = False
    structured_output: bool = False


TEXT_PROVIDER_PRESETS = (
    ProviderPreset("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-5.6-luna", True, True),
    ProviderPreset("openai", "OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", True, True),
    ProviderPreset("glm", "GLM / 智谱", "https://open.bigmodel.cn/api/paas/v4", "glm-5.2"),
    ProviderPreset("deepseek", "DeepSeek", "https://api.deepseek.com", "deepseek-flash"),
    ProviderPreset("custom", "自定义 OpenAI 兼容服务", "", ""),
)

ASR_PROVIDER_PRESETS = (
    ProviderPreset("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-transcribe", True),
    ProviderPreset("openai", "OpenAI", "https://api.openai.com/v1", "gpt-transcribe", True),
    ProviderPreset("custom", "自定义转写兼容服务", "", ""),
)


def provider_preset(provider_id: str, kind: str) -> ProviderPreset | None:
    presets = TEXT_PROVIDER_PRESETS if kind == "text" else ASR_PROVIDER_PRESETS
    return next((item for item in presets if item.id == provider_id), None)


def supports_structured_output(provider_id: str) -> bool:
    preset = provider_preset(provider_id, "text")
    return bool(preset and preset.structured_output)


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")
