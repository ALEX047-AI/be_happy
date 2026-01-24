import pandas as pd
import os, json
from options.config import settings
import pandas as pd

profile_file = f"{settings.DATA}/{settings.profile_file_name}"


crisis_keywords = [
    "умереть", "не хочу жить", "самоубийство", "конец", "смысла нет"
]

profile_fields = [
    "Имя",
    "Пол",
    # "Город",
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


def dict_to_file1(data, file_name_xlsx, format='xlsx'):
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


def dict_to_sheet(data, file_name, format="xlsx"):
    """
    Сохраняем dict или list в файл формата xlsx  ods  csv
    """

    fmt = (format or "xlsx").lower().lstrip(".")
    df = pd.DataFrame(data)

    # форматируем столбец дат
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # пустые колонки в пустую строку
    for col in ("text", "comment"):
        if col in df.columns:
            df[col] = df[col].fillna("")

    # сверяем расширение и формат
    ext = f".{fmt}"
    out_path = file_name if str(file_name).lower().endswith(ext) else f"{file_name}{ext}"

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

    if fmt == "xlsx":
        with pd.ExcelWriter(
            out_path,
            engine="openpyxl",
            datetime_format="yyyy-mm-dd hh:mm",
        ) as writer:
            df.to_excel(writer, index=False)

    elif fmt == "ods":
        with pd.ExcelWriter(out_path, engine="odf") as writer:
            df.to_excel(writer, index=False)

    elif fmt == "csv":
        # ; и utf-8-sig для удобного открытия в Excel
        df.to_csv(out_path, index=False, encoding="utf-8-sig", sep=';', lineterminator="\n")

    else:
        raise ValueError(f"Не поддерживаемый формат: {format}. Принимаются: 'xlsx', 'ods', 'csv'.")

    return out_path

def sheet_to_list0(file_name_xlsx, format='xlsx'):
    """конвертируем xlsx ods csv в dict"""

    df2=pd.read_excel(file_name_xlsx, )
    df2['text'] = df2['text'].fillna("")


    # если есть колонка date - приводим к ISO строке обратно
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        # исправляем на "" если были пустые/битые даты
        df2["date"] = df2["date"].replace("NaT", "")

    df2_list = df2.to_dict(orient="records")
    return df2_list


def sheet_to_list(file_name, format="xlsx", *, csv_sep=";", csv_encoding="utf-8-sig"):
    """конвертируем xlsx/ods/csv в list[dict]"""

    fmt = (format or "xlsx").lower().lstrip(".")

    if fmt in ("xlsx", "xlsm", "xls"):
        df2 = pd.read_excel(file_name, engine="openpyxl")
    elif fmt == "ods":
        df2 = pd.read_excel(file_name, engine="odf")
    elif fmt == "csv":
        df2 = pd.read_csv(file_name, sep=csv_sep, encoding=csv_encoding)
    else:
        raise ValueError(f"Не поддерживаемый формат: {format}. Принимаются: 'xlsx', 'ods', 'csv'.")

    # чтобы пустые тексты не превращались в NaN
    for col in ("text", "comment"):
        if col in df2.columns:
            df2[col] = df2[col].fillna("")

    # если есть колонка date - приводим к ISO строке обратно
    if "date" in df2.columns:
        dt = pd.to_datetime(df2["date"], errors="coerce")

        # Если нет даты то заполняем ""
        df2["date"] = dt.dt.strftime("%Y-%m-%dT%H:%M:%S")
        df2["date"] = df2["date"].fillna("")

    return df2.to_dict(orient="records")

if __name__ == "__main__":

    file_name='diary.json'
    file_name_xlsx='diary.json.xlsx'

    data_dict = load_json(file_name, {})
    dict_to_sheet(data_dict, file_name_xlsx)

    df2_list=sheet_to_list(file_name_xlsx)

    out_json = f"{file_name_xlsx}.json"
    save_json(out_json, df2_list)

    print("Saved:", out_json)