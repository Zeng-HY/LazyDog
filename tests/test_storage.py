import json

from voiceanywhere.models import LatestResult
from voiceanywhere.storage import LocalStore


def test_metrics_do_not_persist_transcript_or_result_text(tmp_path) -> None:
    store = LocalStore(tmp_path)
    result = LatestResult(
        session_id="test",
        transcript="不得持久化的转写",
        result_text="不得持久化的整理结果",
        app_style="chat",
        timings_ms={"stop_to_asr_final": 100},
    )
    store.append_metric(result, "已插入", True)
    text = (tmp_path / "timing.jsonl").read_text(encoding="utf-8")
    assert "不得持久化" not in text
    assert json.loads(text)["inserted"] is True
