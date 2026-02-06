import json
import os
from typing import Any, Optional


class LanguageStore:
    """
    Загружаем языки для интерфейса

    - загружаем JSON из: <data_dir>/<lang>.json
    - Поддерживаются клию через точку (таксономи): "menu.file.exit"
    - В слючае ошибки загружаем язык по умолчанию
    """

    def __init__(self, data_dir: str, default_lang: str = "ru"):
        self.data_dir = data_dir
        self.default_lang = default_lang or "ru"
        self.lang = self.default_lang
        self._data: dict[str, Any] = {}
        self._fallback: dict[str, Any] = {}

    def load(self, lang: str | None):
        lang = (lang or "").strip() or self.default_lang
        self.lang = lang
        self._fallback = self._load_file(self.default_lang)
        self._data = self._fallback if lang == self.default_lang else self._load_file(lang)

    def _load_file(self, lang: str) -> dict[str, Any]:
        path = os.path.join(self.data_dir, f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        v = self._get(self._data, key)
        if v is None:
            v = self._get(self._fallback, key)
        return default if v is None else v

    def t(self, key: str, default: Optional[str] = None, **fmt) -> str:
        v = self.get(key, None)
        if not isinstance(v, str):
            v = default if default is not None else key
        if fmt:
            try:
                return v.format(**fmt)
            except Exception:
                return v
        return v

    @staticmethod
    def _get(obj: Any, dotted: str) -> Any:
        cur = obj
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur
