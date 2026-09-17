import json

from voiceanywhere.playground_contract import PlaygroundParameters, PlaygroundSettings
from voiceanywhere.playground_presets import PlaygroundPresetStore


def test_preset_round_trip_keeps_parameters_but_never_input_or_results(tmp_path) -> None:
    store = PlaygroundPresetStore(tmp_path)
    parameters = PlaygroundParameters(
        "openai/gpt-5.6-luna",
        "strict prompt",
        reasoning_effort="high",
        max_tokens=512,
        settings=PlaygroundSettings(tone="formal", output_language="en"),
    )
    store.save("Formal v1", parameters)
    assert store.load_all()["Formal v1"].parameters == parameters
    raw = json.loads((tmp_path / "playground_presets.json").read_text(encoding="utf-8"))
    serialized = json.dumps(raw, ensure_ascii=False)
    assert "transcript" not in serialized
    assert "nearby_text" not in serialized
    assert "result" not in serialized
    assert "api_key" not in serialized


def test_deleting_a_preset_does_not_affect_other_presets(tmp_path) -> None:
    store = PlaygroundPresetStore(tmp_path)
    parameters = PlaygroundParameters("openai/gpt-5.6-luna", "prompt")
    store.save("A", parameters)
    store.save("B", parameters)
    store.delete("A")
    assert set(store.load_all()) == {"B"}
