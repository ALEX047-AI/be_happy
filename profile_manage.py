import os, json
from options.config import settings

profile_file = f"{settings.DATA}/{settings.profile_file_name}"


crisis_keywords = [
    "умереть", "не хочу жить", "самоубийство", "конец", "смысла нет"
]

profile_fields = [
    "Имя",
    "Пол",
    "Дата рождения",
    "Семейное положение",
    "Родители",
    "Дети",
    'Друзья',
    # "Принимаете ли медикаменты",
    # "Наблюдаетесь ли у врача",
    # "Хобби, интересы",
    "Комментарий",
]



def load_profile():
    if os.path.exists(profile_file):
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_profile(profile_data):
    try:
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
