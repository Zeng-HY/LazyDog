from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voiceanywhere.config import APP_DIR
from voiceanywhere.playground_contract import PlaygroundParameters


PRESETS_FILE = "playground_presets.json"


@dataclass(frozen=True)
class SavedPreset:
    name: str
    parameters: PlaygroundParameters


class PlaygroundPresetStore:
    """Local user-named parameters only; input and result content are deliberately excluded."""

    def __init__(self, root: Path = APP_DIR) -> None:
        self.root = root
        self.path = root / PRESETS_FILE

    def load_all(self) -> dict[str, SavedPreset]:
        raw = self._read()
        presets: dict[str, SavedPreset] = {}
        for name, value in raw.get("presets", {}).items():
            if not isinstance(name, str) or not isinstance(value, dict):
                continue
            try:
                presets[name] = SavedPreset(name, PlaygroundParameters.from_preset(value))
            except ValueError:
                continue
        return presets

    def save(self, name: str, parameters: PlaygroundParameters) -> SavedPreset:
        normalized = name.strip()
        if not normalized:
            raise ValueError("请输入预设名称")
        if len(normalized) > 80:
            raise ValueError("预设名称不能超过 80 个字符")
        raw = self._read()
        presets = raw.setdefault("presets", {})
        presets[normalized] = parameters.as_preset()
        self._write(raw)
        return SavedPreset(normalized, parameters)

    def delete(self, name: str) -> None:
        raw = self._read()
        presets = raw.get("presets", {})
        if isinstance(presets, dict) and name in presets:
            del presets[name]
            self._write(raw)

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("presets", {}), dict):
                return value
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return {"presets": {}}

    def _write(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
