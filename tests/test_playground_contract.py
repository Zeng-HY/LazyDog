import json

import pytest

from voiceanywhere.models import TermEntry
from voiceanywhere.playground_contract import (
    PlaygroundInput,
    PlaygroundParameters,
    PlaygroundSettings,
    terms_for_playground,
)
from voiceanywhere.services import ServiceError, build_playground_request_body, parse_playground_compose_content


def test_playground_request_uses_the_strict_v2_json_contract() -> None:
    settings = PlaygroundSettings(tone="polite", layout="paragraphs", output_language="en", app_style="chat")
    source = PlaygroundInput(
        transcript="订300台，不对，350台。",
        nearby_text="预计周五交货。",
        confirmed_terms=terms_for_playground((TermEntry("Unimed", ("尤尼迈德",), "chat"),), "chat"),
        settings=settings,
    )
    parameters = PlaygroundParameters("openai/gpt-5.6-luna", "strict prompt", settings=settings)
    body = build_playground_request_body(source, parameters)
    payload = json.loads(body["messages"][1]["content"])
    assert set(payload) == {"transcript", "nearby_text", "confirmed_terms", "settings"}
    assert payload["confirmed_terms"] == [{"spoken": "尤尼迈德", "written": "Unimed"}]
    assert payload["settings"]["tone"] == "polite"
    assert payload["settings"]["output_language"] == "en"
    assert "api_key" not in json.dumps(body)


def test_terms_only_map_aliases_from_the_active_scope() -> None:
    terms = (
        TermEntry("Global", ("全局别名",), "global"),
        TermEntry("Chat", ("聊天别名",), "chat"),
    )
    assert terms_for_playground(terms, "neutral") == (terms_for_playground(terms[:1], "neutral")[0],)
    assert [item.spoken for item in terms_for_playground(terms, "chat")] == ["全局别名", "聊天别名"]


def test_ab_parameter_snapshots_do_not_share_settings() -> None:
    source = PlaygroundInput("同一段口述", "", (), PlaygroundSettings())
    a = PlaygroundParameters("openai/gpt-5.6-luna", "prompt A", settings=PlaygroundSettings(tone="preserve"))
    b = PlaygroundParameters(
        "openai/gpt-5.6-luna",
        "prompt B",
        settings=PlaygroundSettings(edit_level="light", tone="formal", layout="paragraphs"),
    )
    payload_a = json.loads(build_playground_request_body(source, a)["messages"][1]["content"])
    payload_b = json.loads(
        build_playground_request_body(
            PlaygroundInput(source.transcript, source.nearby_text, source.confirmed_terms, b.settings), b
        )["messages"][1]["content"]
    )
    assert payload_a["settings"] == PlaygroundSettings(tone="preserve").as_request_settings()
    assert payload_b["settings"]["edit_level"] == "light"
    assert payload_b["settings"]["tone"] == "formal"
    assert payload_a["settings"]["layout"] == "preserve"


def test_auto_settings_are_valid_internal_values() -> None:
    settings = PlaygroundSettings(edit_level="auto", layout="auto")
    assert settings.as_request_settings()["edit_level"] == "auto"
    assert settings.as_request_settings()["layout"] == "auto"


def test_strict_v2_allows_empty_text_and_object_attention() -> None:
    empty = parse_playground_compose_content('{"text":"","attention":[]}')
    assert empty.text == ""
    result = parse_playground_compose_content(
        '{"text":"保留原文。","attention":[{"span":"li工","issue":"无法区分姓名写法"}]}'
    )
    assert result.attention[0].span == "li工"


@pytest.mark.parametrize(
    "content",
    [
        '{"text":"x","attention":["疑点"]}',
        '{"text":"x","attention":[{"span":"","issue":"疑点"}]}',
        '{"text":"x","attention":[{"span":"a","issue":"b","extra":"x"}]}',
        '{"text":"x","attention":[{"span":"a","issue":"b"},{"span":"c","issue":"d"},{"span":"e","issue":"f"}]}',
    ],
)
def test_strict_v2_rejects_invalid_attention_contract(content: str) -> None:
    with pytest.raises(ServiceError):
        parse_playground_compose_content(content)
