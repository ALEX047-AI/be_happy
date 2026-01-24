import pandas as pd
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
    "Друзья",
    "Домашние животные",
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


def dict_to_xlsx(data, file_name_xlsx):
    """конвертируем из dict to xlsx"""

    df = pd.DataFrame(data)
    # если есть колонка date - превратим ISO-строку в datetime, чтобы Excel показывал нормальную дату
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # чтобы пустые тексты не превращались в NaN
    for col in ("text", "comment"):
        if col in df.columns:
            df[col] = df[col].fillna("")

    # out_xlsx = f"{file_name}.xlsx"
    with pd.ExcelWriter(file_name_xlsx, engine="openpyxl", datetime_format="yyyy-mm-dd hh:mm") as writer:
        df.to_excel(writer, index=False)


def xlsx_to_list(file_name_xlsx):
    """конвертируем xlsx в dict"""

    df2=pd.read_excel(file_name_xlsx, )
    df2['text'] = df2['text'].fillna("")


    # если есть колонка date - приводим к ISO строке обратно
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        # если были пустые/битые даты - они станут NaT -> "NaT", исправим на ""
        df2["date"] = df2["date"].replace("NaT", "")

    df2_list = df2.to_dict(orient="records")
    return df2_list

if __name__ == "__main__":

    file_name='diary.json'
    file_name_xlsx='diary.json.xlsx'

    data_dict = load_json(file_name, {})
    dict_to_xlsx(data_dict, file_name_xlsx)

    df2_list=xlsx_to_list(file_name_xlsx)

    out_json = f"{file_name_xlsx}.json"
    save_json(out_json, df2_list)

    print("Saved:", out_json)