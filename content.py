import json
import os
from typing import Any


class ContentStore:
    """
    Загружаем языковые зависимости.
    Только для LLM

    Структура каталогов:

      data/content/
        articles.ru.json
        articles.en.json
        ...
        crisis_keywords.ru.json
        ...
        system_prompt.ru.txt
        ...

    articles.<lang>.json format:
      {
        "main_articles": [...],
        "support_phrases": [...]
      }
    """

    def __init__(self, content_dir: str, default_lang: str = "ru"):
        self.content_dir = content_dir
        self.default_lang = default_lang or "ru"

    def _read_json(self, filename: str) -> dict[str, Any]:
        path = os.path.join(self.content_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _read_txt(self, filename: str) -> str:
        path = os.path.join(self.content_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def get_articles_pack(self, lang: str | None) -> dict[str, Any]:
        lang = (lang or "").strip() or self.default_lang
        pack = self._read_json(f"articles.{lang}.json")
        if not pack:
            pack = self._read_json(f"articles.{self.default_lang}.json")
        return pack or {}

    def get_support_phrases(self, lang: str | None):
        pack = self.get_articles_pack(lang)
        phrases = pack.get("support_phrases", [])
        if isinstance(phrases, dict):
            phrases = list(phrases.keys())
        return phrases if isinstance(phrases, list) else []

    def get_main_articles(self, lang: str | None):
        pack = self.get_articles_pack(lang)
        arts = pack.get("main_articles", [])
        if isinstance(arts, dict):
            arts = list(arts.keys())
        return arts if isinstance(arts, list) else []

    def get_crisis_keywords(self, lang: str | None):
        lang = (lang or "").strip() or self.default_lang
        pack = self._read_json(f"crisis_keywords.{lang}.json")
        if not pack:
            pack = self._read_json(f"crisis_keywords.{self.default_lang}.json")
        kws = pack.get("keywords", [])
        return kws if isinstance(kws, list) else []

    def get_system_prompt(self, lang: str | None, default_prompt: str = "") -> str:
        lang = (lang or "").strip() or self.default_lang
        s = self._read_txt(f"system_prompt.{lang}.txt")
        if not s:
            s = self._read_txt(f"system_prompt.{self.default_lang}.txt")
        return s.strip() or (default_prompt or "").strip()
