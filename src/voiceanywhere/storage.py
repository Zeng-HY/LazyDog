from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from voiceanywhere.config import APP_DIR
from voiceanywhere.models import LatestResult


class LocalStore:
    """Only settings, opt-in cases, and body-free timing/status events are persisted."""

    def __init__(self, root: Path = APP_DIR) -> None:
        self.root = root
        self.metrics_path = root / "timing.jsonl"
        self.cases_dir = root / "cases"

    def append_metric(self, result: LatestResult, status: str, inserted: bool) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "at_unix": int(time.time()),
            "session_id": result.session_id,
            "status": status,
            "inserted": inserted,
            "app_style": result.app_style,
            "model_config": {"asr": "openai/whisper-large-v3", "compose": "openai/gpt-5.6-luna"},
            "timings_ms": result.timings_ms,
        }
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def save_case(self, result: LatestResult, user_final_text: str, issue: str) -> Path:
        if not result.audio_wav:
            raise ValueError("当前结果没有可保存的录音")
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        case_id = f"case_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        audio_path = self.cases_dir / f"{case_id}.wav"
        json_path = self.cases_dir / f"{case_id}.json"
        audio_path.write_bytes(result.audio_wav)
        payload = {
            "case_id": case_id,
            "audio_path": audio_path.name,
            "transcript": result.transcript,
            "result": result.result_text,
            "user_final_text": user_final_text,
            "issue": issue,
            "app_category": result.app_style,
            "nearby_text": "",
            "active_terms": [],
            "model_config_label": "openai/whisper-large-v3 + openai/gpt-5.6-luna",
            "timings_ms": result.timings_ms,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return json_path
