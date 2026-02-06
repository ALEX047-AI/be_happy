import pandas as pd
# from pandas import RangeIndex

data = {'2025-12-14T08:00:00': {'mood': 5}, '2025-12-15T08:00:00': {'mood': 6}, '2025-12-15T14:00:00': {'mood': 6}, '2026-01-29T14:00:00': {'mood': 3}, '2026-01-29T20:00:00': {'mood': 5}, '2026-01-31T14:00:00': {'mood': 4}, '2026-02-01T08:00:00': {'mood': 3}, '2026-02-02T08:00:00': {'mood': 8, 'text': 'нормик'}}


def dict_to_sheet(data, file_name, format="xlsx", source_type: str|None = None):
    """
    Сохраняем dict или list в файл формата xlsx  ods  csv
    """
    if isinstance(data, dict):
        if source_type != 'diary':
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
    if source_type == 'diary':
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
    print(df)
    df = df.iloc[:, :2].fillna("")

    if data_type != 'diary':
        # Убираем лишние пробелы на концах
        df[0] = df[0].astype(str).str.strip()
        df[1] = df[1].apply(lambda x: x.strip() if isinstance(x, str) else x)

        # Убираем пустые значения
        df = df[df[0] != ""]
        return dict(zip(df[0].tolist(), df[1].tolist()))
    else:
        print(df)
        return df.to_dict(orient='index')

# dict_to_sheet(data, 'diary_text_new', source_type='diary')
print(sheet_to_dict('diary_text_new.xlsx', data_type='diary'))
