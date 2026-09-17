from voiceanywhere.config import DpapiSecretStore, SettingsStore, format_terms, parse_terms
from voiceanywhere.models import AppSettings, ProviderSettings, TermEntry, VoiceMode


def test_terms_parse_and_format_round_trip() -> None:
    parsed = parse_terms("Unimed | 尤尼迈德, 优尼迈德 | global\nBTR |  | chat")
    assert parsed == [
        TermEntry("Unimed", ("尤尼迈德", "优尼迈德"), "global"),
        TermEntry("BTR", (), "chat"),
    ]
    assert parse_terms(format_terms(parsed)) == parsed


def test_settings_round_trip(tmp_path) -> None:
    store = SettingsStore(tmp_path)
    expected = AppSettings(
        microphone=3,
        hotkey="Ctrl+Alt+F8",
        mode=VoiceMode.TRANSCRIBE_ONLY,
        output_language="en",
        terms=[TermEntry("510(k)", ("五幺零K",), "global")],
    )
    store.save(expected)
    assert store.load() == expected


def test_settings_store_accepts_legacy_string_mode(tmp_path) -> None:
    store = SettingsStore(tmp_path)
    store.save(AppSettings(mode="faithful"))
    assert store.load().mode == VoiceMode.FAITHFUL


def test_provider_settings_round_trip(tmp_path) -> None:
    store = SettingsStore(tmp_path)
    expected = AppSettings(
        providers=ProviderSettings(
            text_provider="glm",
            text_base_url="https://open.bigmodel.cn/api/paas/v4",
            text_model="glm-5.2",
            asr_provider="openai",
            asr_base_url="https://api.openai.com/v1",
            asr_model="gpt-transcribe",
        )
    )
    store.save(expected)
    assert store.load().providers == expected.providers


def test_asr_key_only_reuses_text_key_for_the_same_provider(tmp_path) -> None:
    store = SettingsStore(tmp_path)
    store.secrets.set("text_api_key", "glm-key")
    shared = ProviderSettings(text_provider="openai", asr_provider="openai")
    separate = ProviderSettings(text_provider="glm", asr_provider="openrouter")
    assert store.asr_api_key(shared) == "glm-key"
    assert store.asr_api_key(separate) is None


def test_dpapi_secret_is_readable_only_for_current_user_and_not_plaintext(tmp_path) -> None:
    secrets = DpapiSecretStore(tmp_path)
    secrets.set("openrouter_api_key", "unit-test-secret")
    assert secrets.get("openrouter_api_key") == "unit-test-secret"
    assert "unit-test-secret" not in (tmp_path / "secrets.json").read_text(encoding="utf-8")
