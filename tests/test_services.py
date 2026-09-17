import pytest
import httpx

from voiceanywhere.services import ASR_MODEL, OpenRouterClient, ServiceError, parse_compose_content


def test_structured_compose_content_is_strict_and_trimmed() -> None:
    result = parse_compose_content('{"text":"  订350台。  ","attention":[" 请确认型号 "]}')
    assert result.text == "订350台。"
    assert result.attention == ("请确认型号",)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"text":"x"}',
        '{"text":"","attention":[]}',
        '{"text":"x","attention":["1","2","3"]}',
    ],
)
def test_invalid_structured_compose_content_never_becomes_insertable(content: str) -> None:
    with pytest.raises(ServiceError):
        parse_compose_content(content)


def test_transcription_uses_gpt_transcribe_and_the_caller_key() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "测试转写"})

    client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))
    service = OpenRouterClient(client=client)
    result = service.transcribe(b"RIFF", "same-openrouter-key", 1.0)
    assert ASR_MODEL == "openai/gpt-transcribe"
    assert captured["authorization"] == "Bearer same-openrouter-key"
    assert ASR_MODEL.encode() in captured["body"]
    assert result.text == "测试转写"
