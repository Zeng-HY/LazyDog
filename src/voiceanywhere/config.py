from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import asdict
from pathlib import Path
from typing import Any

from voiceanywhere.models import AppSettings, TermEntry, VoiceMode


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VoiceAnywhere"
CONFIG_FILE = "settings.json"
SECRETS_FILE = "secrets.json"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob_from_bytes(value: bytes) -> tuple[DataBlob, Any]:
    buffer = ctypes.create_string_buffer(value)
    return DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


class DpapiSecretStore:
    """Small current-user DPAPI store. It never returns encrypted text as a key."""

    def __init__(self, root: Path = APP_DIR) -> None:
        self.root = root
        self.path = root / SECRETS_FILE

    def get(self, name: str) -> str | None:
        data = self._read_file()
        value = data.get(name)
        if not isinstance(value, str):
            return None
        try:
            return self._unprotect(base64.b64decode(value)).decode("utf-8")
        except Exception:
            return None

    def set(self, name: str, value: str) -> None:
        data = self._read_file()
        data[name] = base64.b64encode(self._protect(value.encode("utf-8"))).decode("ascii")
        self._write_file(data)

    def delete(self, name: str) -> None:
        data = self._read_file()
        if name in data:
            del data[name]
            self._write_file(data)

    def _read_file(self) -> dict[str, str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_file(self, data: dict[str, str]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _protect(value: bytes) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI is only available on Windows")
        input_blob, input_buffer = _blob_from_bytes(value)
        output_blob = DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        if not crypt32.CryptProtectData(
            ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)
            del input_buffer

    @staticmethod
    def _unprotect(value: bytes) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI is only available on Windows")
        input_blob, input_buffer = _blob_from_bytes(value)
        output_blob = DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        if not crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)
            del input_buffer


class SettingsStore:
    def __init__(self, root: Path = APP_DIR) -> None:
        self.root = root
        self.path = root / CONFIG_FILE
        self.secrets = DpapiSecretStore(root)

    def load(self) -> AppSettings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return AppSettings()
        terms = [self._term_from_dict(item) for item in raw.get("terms", []) if isinstance(item, dict)]
        terms = [term for term in terms if term is not None]
        mode = VoiceMode(raw.get("mode", VoiceMode.FAITHFUL.value)) if raw.get("mode") in {
            item.value for item in VoiceMode
        } else VoiceMode.FAITHFUL
        output_language = raw.get("output_language", "follow")
        if output_language not in {"follow", "zh", "en"}:
            output_language = "follow"
        microphone = raw.get("microphone")
        return AppSettings(
            microphone=microphone if isinstance(microphone, int) else None,
            hotkey=raw.get("hotkey") if isinstance(raw.get("hotkey"), str) else "Ctrl+Alt+Space",
            mode=mode,
            output_language=output_language,
            terms=terms,
        )

    def save(self, settings: AppSettings) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        mode = settings.mode if isinstance(settings.mode, VoiceMode) else VoiceMode(str(settings.mode))
        payload["mode"] = mode.value
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _term_from_dict(value: dict[str, Any]) -> TermEntry | None:
        canonical = value.get("canonical")
        if not isinstance(canonical, str) or not canonical.strip():
            return None
        aliases = value.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        scope = value.get("scope", "global")
        if scope not in {"global", "chat", "email", "neutral"}:
            scope = "global"
        return TermEntry(canonical.strip(), tuple(str(item).strip() for item in aliases if str(item).strip()), scope)


def parse_terms(text: str) -> list[TermEntry]:
    """Parse one user-maintained term per line: standard | aliases | scope."""
    terms: list[TermEntry] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split("|")]
        canonical = fields[0]
        if not canonical:
            continue
        aliases = tuple(item.strip() for item in (fields[1].split(",") if len(fields) > 1 else []) if item.strip())
        scope = fields[2].lower() if len(fields) > 2 else "global"
        if scope not in {"global", "chat", "email", "neutral"}:
            raise ValueError(f"词条范围无效：{scope}。可用 global、chat、email 或 neutral。")
        terms.append(TermEntry(canonical, aliases, scope))
    return terms


def format_terms(terms: list[TermEntry]) -> str:
    return "\n".join(
        f"{term.canonical} | {', '.join(term.aliases)} | {term.scope}" for term in terms
    )
