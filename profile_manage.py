import os, json
import pandas as pd
from pandas.api.types import is_string_dtype

from options.config import settings
from auth_storage import auth_manager

profile_file = f"{settings.DATA}/{settings.profile_file_name}"


crisis_keywords = [
    "умереть", "не хочу жить", "самоубийство", "конец", "смысла нет"
]

profile_fields = [
    "Имя",
    "Пол",
    "Город",
    "Дата рождения",
    "Семейное положение",
    "Родители",
    "Дети",
    "Друзья",
    "Домашние животные",
    # "Принимаете ли медикаменты",
    # "Наблюдаетесь ли у врача",
    "Хобби, интересы",
    "Комментарий",
]
diary_fields = ['date', 'mood', 'text']

def load_profile():
    """Загружает профиль текущего вошедшего пользователя из зашифрованного хранилища."""
    try:
        return auth_manager.load_profile(default={})
    except Exception:
        return {}


def save_profile(profile_data):
    """Сохраняет профиль текущего вошедшего пользователя в зашифрованное хранилище."""
    try:
        auth_manager.save_profile(profile_data)
        return True
    except Exception:
        return False


def load_diary(default=None):
    if default is None:
        default = {}
    try:
        return auth_manager.load_diary(default=default)
    except Exception:
        return default


def save_diary(diary_data):
    try:
        auth_manager.save_diary(diary_data)
        return True
    except Exception:
        return False


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def dict_to_file1(data, file_name_xlsx, format='xlsx'):
    """Преобразуем dict в xlsx."""

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


def dict_to_sheet0(data, file_name, format="xlsx"):
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

def dict_to_sheet1(data, file_name, format="xlsx"):
    """
    Сохраняем dict или list в файл формата xlsx  ods  csv
    """
    if isinstance(data, dict):
        data = [data]
        use_index = True
        use_header = False
        do_transpose = True
    else:
        use_index = False
        use_header = True
        do_transpose = False

    fmt = (format or "xlsx").lower().lstrip(".")
    df = pd.DataFrame(data)
    # print(df)
    # Если это словарь (напрмер Профиль), то переворачиваем
    if do_transpose:
        df = df.T

    # форматируем столбец дат
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # пустые колонки в пустую строку
    for col in ("text", "comment", "Комментарий"):
        if col in df.columns:
            df[col] = df[col].fillna("")

    # сверяем расширение и формат
    ext = f".{fmt}"
    out_path = file_name if str(file_name).lower().endswith(ext) else f"{file_name}{ext}"

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

    engines = {"xlsx": "openpyxl", "ods": "odf"}

    if fmt in ("xlsx", "ods"):
        with pd.ExcelWriter(
            out_path,
            engine=engines[fmt],
            datetime_format="yyyy-mm-dd hh:mm",
        ) as writer:
            df.to_excel(writer, index=use_index, header=use_header)

        """ elif fmt == "ods":
            with pd.ExcelWriter(out_path, datetime_format="yyyy-mm-dd hh:mm", engine="odf") as writer:
                df.to_excel(writer, index=use_index, header=use_header) """

    elif fmt == "csv":
        # ; и utf-8-sig для удобного открытия в Excel
        df.to_csv(out_path, index=use_index, encoding="utf-8-sig", sep=';', lineterminator="\n",  header=use_header)

    else:
        raise ValueError(f"Не поддерживаемый формат: {format}. Принимаются: 'xlsx', 'ods', 'csv'.")

    return out_path


def dict_to_sheet(data, file_name, format="xlsx", data_type: str|None = None):
    """
    Сохраняем dict или list в файл формата xlsx  ods  csv
    Указать data_type = 'diary' для Дневника
    """
    if isinstance(data, dict):
        if data_type != 'diary':
            data = [data]
            use_index = True
            use_header = False
        else:
            use_index = False
            use_header = True
        do_transpose = True
    else:
        use_index = False
        use_header = True
        do_transpose = False

    fmt = (format or "xlsx").lower().lstrip(".")
    df = pd.DataFrame(data)
    # Если это словарь (напрмер Профиль), то переворачиваем
    if do_transpose:
        df = df.T
    # if type(df.index) != RangeIndex:
    if data_type == 'diary':
        df.index.name = 'date'
        df.reset_index(inplace=True)

    # форматируем столбец дат
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # пустые колонки в пустую строку
    for col in ("text", "comment", "Комментарий"):
        if col in df.columns:
            df[col] = df[col].fillna("")

    # сверяем расширение и формат
    ext = f".{fmt}"

    if file_name is None:
        return

    out_path = file_name if str(file_name).lower().endswith(ext) else f"{file_name}{ext}"

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")

    engines = {"xlsx": "openpyxl", "ods": "odf"}

    if fmt in ("xlsx", "ods"):
        with pd.ExcelWriter(
            out_path,
            engine=engines[fmt],
            datetime_format="yyyy-mm-dd hh:mm",
        ) as writer:
            df.to_excel(writer, index=use_index, header=use_header)

        """ elif fmt == "ods":
            with pd.ExcelWriter(out_path, datetime_format="yyyy-mm-dd hh:mm", engine="odf") as writer:
                df.to_excel(writer, index=use_index, header=use_header) """

    elif fmt == "csv":
        # ; и utf-8-sig для удобного открытия в Excel
        df.to_csv(out_path, index=use_index, encoding="utf-8-sig", sep=';', lineterminator="\n",  header=use_header)

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

    # если есть колонка date - приводим к ISO строке обратно
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Если нет данных то заполняем ""
    df2 = df2.fillna("")

    # Убираем лишние пробелы на концах
    for col in df2.columns:
        if is_string_dtype(df2[col]):
            df2[col] = df2[col].astype(str).str.strip()

    # Убираем пустые значения
    first_col = df2.columns[0]
    df2 = df2[df2[first_col] != ""]

    return df2.to_dict(orient="records")

def sheet_to_dict0(file_name, format="xlsx", *, csv_sep=";", csv_encoding="utf-8-sig"):
    fmt = (format or "xlsx").lower().lstrip(".")

    if fmt in ("xlsx", "xlsm", "xls"):
        df = pd.read_excel(file_name, engine="openpyxl", header=None)
    elif fmt == "ods":
        df = pd.read_excel(file_name, engine="odf", header=None)
    elif fmt == "csv":
        df = pd.read_csv(file_name, sep=csv_sep, encoding=csv_encoding, header=None)
    else:
        raise ValueError(f"Не поддерживаемый формат: {format}. Принимаются: 'xlsx', 'ods', 'csv'.")

    # преобразуем NaN в ""
    df = df.iloc[:, :2].fillna("")

    # Убираем лишние пробелы на концах
    df[0] = df[0].astype(str).str.strip()
    df[1] = df[1].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # Убираем пустые значения
    df = df[df[0] != ""]

    return dict(zip(df[0].tolist(), df[1].tolist()))


def sheet_to_dict(file_name, format="xlsx", *, csv_sep=";", csv_encoding="utf-8-sig", data_type: str|None = None):
    fmt = (format or "xlsx").lower().lstrip(".")

    header = 0 if data_type == 'diary' else None

    if fmt in ("xlsx", "xlsm", "xls"):
        df = pd.read_excel(file_name, engine="openpyxl", header=header)
    elif fmt == "ods":
        df = pd.read_excel(file_name, engine="odf", header=header)
    elif fmt == "csv":
        df = pd.read_csv(file_name, sep=csv_sep, encoding=csv_encoding, header=header)
    else:
        raise ValueError(f"Не поддерживаемый формат: {format}. Принимаются: 'xlsx', 'ods', 'csv'.")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        df.set_index('date', inplace=True)
    # преобразуем NaN в ""
    # column_number = 3 if data_type == 'diary' else 2
    df = df.iloc[:, :2].fillna("")

    if data_type != 'diary':
        # Убираем лишние пробелы на концах
        df[0] = df[0].astype(str).str.strip()
        df[1] = df[1].apply(lambda x: x.strip() if isinstance(x, str) else x)

        # Убираем пустые значения
        df = df[df[0] != ""]
        return dict(zip(df[0].tolist(), df[1].tolist()))
    else:
        return df.to_dict(orient='index')

if __name__ == "__main__":

    file_name='diary.json'
    file_name_xlsx='diary.json.xlsx'

    data_dict = load_json(file_name, {})
    dict_to_sheet(data_dict, file_name_xlsx)

    df2_list=sheet_to_list(file_name_xlsx)

    out_json = f"{file_name_xlsx}.json"
    save_json(out_json, df2_list)

    print("Saved:", out_json)