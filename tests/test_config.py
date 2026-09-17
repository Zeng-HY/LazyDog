from voiceanywhere.config import DpapiSecretStore, SettingsStore, format_terms, parse_terms
from voiceanywhere.models import AppSettings, TermEntry, VoiceMode


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


def test_dpapi_secret_is_readable_only_for_current_user_and_not_plaintext(tmp_path) -> None:
    secrets = DpapiSecretStore(tmp_path)
    secrets.set("openrouter_api_key", "unit-test-secret")
    assert secrets.get("openrouter_api_key") == "unit-test-secret"
    assert "unit-test-secret" not in (tmp_path / "secrets.json").read_text(encoding="utf-8")
