import pytest

from voiceanywhere.services import ServiceError, parse_compose_content


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
