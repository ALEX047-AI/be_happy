import httpx
from zoneinfo import ZoneInfo
import html, json
import threading

from datetime import datetime, timedelta

from options.config import settings

class SharedData:
    def __init__(self):
        self.data: list = []

    def get(self):
        return self.data

    def set(self, value):
        self.data = value


class EVENTS_INFO:

    def __init__(self):
        # self.base_url = 'https://api.timepad.ru/v1'
        self.base_url = settings.TIMEPAD_BASE_URL
        self.token = settings.TIMEPAD_TOKEN
        # self.token = global_token


    def get_events_info(self, from_day: str = None, to_day: str|int = 3, city: str = "Москва", limit: int = 10,
                        timeout=30.0, category_ids_exclude: list|None = None) -> list:
        """
        from_day / to_day: '2026-01-24T11:00'
        """
        # curl -X GET "https://api.timepad.ru/v1/dictionary/event_categories"
        # curl -X GET "https://api.timepad.ru/v1/events?limit=10&sort=%2Bid
        # &cities=%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0
        # &access_statuses=public&moderation_statuses=featured%2Cshown%2Cnot_moderated
        # &price_max=1
        # &starts_at_min=2026-01-24&starts_at_max=2026-01-31"
        # -H  "accept: application/json" -H  "authorization: Bearer ***********************"

        # curl -X GET "https://api.timepad.ru/v1/events?limit=10&sort=%2Bid&cities=%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0&access_statuses=public&moderation_statuses=featured%2Cshown%2Cnot_moderated&price_max=1&starts_at_min=2026-01-24&starts_at_max=2026-01-31" -H  "accept: application/json" -H  "authorization: Bearer "
        # curl -X GET "https://api.timepad.ru/v1/events?limit=100&sort=%2Bid&category_ids_exclude=217&cities=%D0%9E%D1%80%D0%B5%D0%BD%D0%B1%D1%83%D1%80%D0%B3&access_statuses=public&moderation_statuses=featured%2Cshown%2Cnot_moderated&starts_at_min=2026-01-26&starts_at_max=2026-02-04" -H  "accept: application/json" -H  "authorization: Bearer "
        # url = "https://api.timepad.ru/v1/events"
        method = 'events'
        url = f'{self.base_url}/{method}'
        if category_ids_exclude is None:
            category_ids_exclude = [217]

        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.token}",
        }

        if from_day is None:
            from_day_dt = datetime.now()
            from_day_iso = from_day_dt.isoformat()
        else:
            from_day_iso = from_day
            from_day_dt = datetime.fromisoformat(from_day_iso)

        if isinstance(to_day, int):
            to_day_td = from_day_dt+timedelta(days=to_day)
            to_day_iso = to_day_td.isoformat()
        else:
            to_day_iso = to_day

        params = {
            "limit": limit,
            "sort": "+id",
            "cities": city,
            "access_statuses": "public",
            "moderation_statuses": "featured,shown,not_moderated",
            "price_max": 1,
            "starts_at_min": from_day_iso,
            "starts_at_max": to_day_iso,
            "category_ids_exclude": category_ids_exclude
        }

        try:
            with httpx.Client(verify=False, timeout=timeout) as client:
                r = client.get(url, headers=headers, params=params)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            print(f'Возникла ошибка при получении данных events {repr(e)}')
            return {}

    def compile_events_info(self, data, view='simple', unescape=True) -> dict:
        events_doc = {}
        # events_doc = {item_id: in data.get("values", []) if (item_id := item.get("id")) is not None}
        data_list = data.get("values", [])
        print(f'Получено данных всего {len(data_list)}')
        for item in data_list:
            try:
                if all((
                    (item_id := item.get("id")),
                    (name := item.get("name")),
                    (starts_at := item.get("starts_at")),
                )):
                    try:
                        if unescape:
                            name = html.unescape((name or "").strip())
                    except Exception as e:
                        continue
                    if not name:
                        continue
                    if view == 'simple':
                        events_doc[item_id] = {name: starts_at}
                    else:
                        events_doc[item_id] = {
                            "id": item_id,
                            "name": name,
                            "starts_at": starts_at
                        }
                    # print(item.get("id"), "-", item.get("name"))
            except Exception as e:
                ...
        return list(events_doc.values())

    def format_events(self, events_doc: list[dict], limit: int = 10, unescape=True) -> str:
        """Сделать красивый список ближайших событий"""
        items = []
        for d in (events_doc or []):
            if not isinstance(d, dict):
                continue
            for title, dt_str in d.items():
                if unescape:
                    title = html.unescape((title or "").strip())
                dt_str = (dt_str or "").strip()
                if not title or not dt_str:
                    continue
                try:
                    # пример 2026-01-24T11:00:00+0300
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
                except Exception:
                    dt = None
                    continue

                items.append((dt, title, dt_str))

        # сначала те, где есть дата
        items.sort(key=lambda x: (x[0] is None, x[0] or x[2]))

        lines = []
        for dt, title, dt_str in items[:limit]:
            pretty = dt.strftime("%d.%m.%Y %H:%M")
            lines.append(f"- {title} — {pretty}")
        answer = "\n".join(lines)
        print(f'format_events = {answer}')
        return answer


    def get_categories_info(self, from_day: str = None, to_day: str|int = 3, city: str = "Москва", limit: int = 10, timeout=30.0):
        """
        список категорий
        """
        # curl -X GET "https://api.timepad.ru/v1/dictionary/event_categories" -H  "accept: application/json" -H  "authorization: Bearer

        # curl -X GET "https://api.timepad.ru/v1/dictionary/event_categories"

        # url = "https://api.timepad.ru/v1/events"
        # current_tz = settings.tz
        method = 'event_categories'
        url = f'{self.base_url}/{method}'
        current_tz = ZoneInfo("Europe/Moscow")


        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.token}",
        }

        if from_day is None:
            from_day_dt = datetime.now()
            from_day_iso = from_day_dt.isoformat()
        else:
            from_day_iso = from_day
            from_day_dt = datetime.fromisoformat(from_day_iso)

        if isinstance(to_day, int):
            to_day_td = from_day_dt+timedelta(days=to_day)
            to_day_iso = to_day_td.isoformat()
        else:
            to_day_iso = to_day

        params = {
            "limit": limit,
            "sort": "+id",
            "cities": city,
            "access_statuses": "public",
            "moderation_statuses": "featured,shown,not_moderated",
            "price_max": 1,
            "starts_at_min": from_day_iso,
            "starts_at_max": to_day_iso,
        }

        with httpx.Client(verify=False, timeout=timeout) as client:
            r = client.get(url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()

        {
            "values": [
                {
                    "id": 217,
                    "name": "Бизнес",
                    "tag": "business"
                },
                {
                    "id": 374,
                    "name": "Кино",
                    "tag": "cinema"
                },
                {
                    "id": 376,
                    "name": "Спорт",
                    "tag": "sport"
                },
                {
                    "id": 379,
                    "name": "Для детей",
                    "tag": "kids"
                },
                {
                    "id": 382,
                    "name": "Иностранные языки",
                    "tag": "languages"
                },
                {
                    "id": 399,
                    "name": "Красота и здоровье",
                    "tag": "beauty"
                },
                {
                    "id": 452,
                    "name": "ИТ и интернет",
                    "tag": "it"
                },
                {
                    "id": 453,
                    "name": "Психология и самопознание",
                    "tag": "psychology"
                },
                {
                    "id": 456,
                    "name": "Еда",
                    "tag": "food"
                },
                {
                    "id": 457,
                    "name": "Вечеринки",
                    "tag": "party"
                },
                {
                    "id": 458,
                    "name": "Выставки",
                    "tag": "exhibition"
                },
                {
                    "id": 459,
                    "name": "Театры",
                    "tag": "theater"
                },
                {
                    "id": 460,
                    "name": "Концерты",
                    "tag": "concert"
                },
                {
                    "id": 461,
                    "name": "Экскурсии и путешествия",
                    "tag": "trip"
                },
                {
                    "id": 462,
                    "name": "Другие события",
                    "tag": "other_event"
                },
                {
                    "id": 463,
                    "name": "Другие развлечения",
                    "tag": "other_entertainment"
                },
                {
                    "id": 524,
                    "name": "Хобби и творчество",
                    "tag": "hobby"
                },
                {
                    "id": 525,
                    "name": "Искусство и культура",
                    "tag": "art"
                },
                {
                    "id": 1315,
                    "name": "Образование за рубежом",
                    "tag": "education_abroad"
                },
                {
                    "id": 1940,
                    "name": "Гражданские проекты",
                    "tag": "civil"
                },
                {
                    "id": 2335,
                    "name": "Интеллектуальные игры",
                    "tag": "intellekt"
                },
                {
                    "id": 2465,
                    "name": "Наука",
                    "tag": "science"
                }
            ]
        }
# shared_data = SharedData()

class EVENTS_INFO_DYNAMIC(threading.Thread):
    def __init__(self, shared_data: SharedData, unescape = True, view='full', finished_item: bool = False, daemon: bool = True):
        """Не загружает данные автоматически. нужно указать город и проставить set"""
        super().__init__(daemon=daemon)
        # self._events_doc = events_doc or []  # список событий который является общим с ЛЛМ
        self.shared_data = shared_data

        self.unescape = unescape
        self.view = view

        self.last_data = {}
        self.events_compiled_dict = {}
        self.events_text = ""

        self.event_info = EVENTS_INFO()
        self.renew_event = threading.Event() # если установлен то нужно обновить данные
        self.renew_event.clear()
        self.current_query_param = {}

    def set_query_param(self,
        param: dict = dict(
                from_day = None,
                to_day = None,
                city = "Москва",
                limit = 10,
                timeout = 30
            ),
        renew: bool = False
        ):
        self.current_query_param = {item: value for item, value in param.items() if value is not None}
        if renew:
            self.reniew_events()

    def set_compiled_param(self, unescape = True, view='full'):
        self.unescape = unescape
        self.view = view

    def reniew_events(self):
        self.renew_event.set()

    def run(self):
        while True:
            self.renew_event.wait()
            self.renew_event.clear()
            self.last_data = self.event_info.get_events_info(**self.current_query_param)
            """     # from_day="2026-01-24",
                # to_day="2026-01-31",
                city="Москва",
                limit=10,
            ) """

            # пример: вывести первые события (как есть)
            self.events_compiled_dict = self.event_info.compile_events_info(self.last_data, unescape=self.unescape, view=self.view)
            self.shared_data.set(self.events_compiled_dict)
            print(self.events_compiled_dict)
            # self.events_text = self.event_info.format_events(self.events_compiled_dict, unescape=False)
            # print(self.events_text)
            # print(self.event_info.compile_events_info(self.last_data, unescape=True))

if __name__ == "__main__":
    # тестируем только запрос без многозадачности
    if False:
        event_info = EVENTS_INFO()
        data = event_info.get_events_info(
            # from_day="2026-01-24",
            # to_day="2026-01-31",
            city="Москва",
            limit=10,
        )

        # пример: вывести первые события (как есть)
        print(event_info.compile_events_info(data, unescape=True, view='full'))
        print(event_info.format_events(event_info.compile_events_info(data), unescape=False))
        print(event_info.compile_events_info(data, unescape=True))
        """ for item in data.get("values", []):
            print(item.get("id"), "-", item.get("name")) """
    else:
        shared_data = SharedData()
        ivents_renew = EVENTS_INFO_DYNAMIC(shared_data)
        ivents_renew.start()
        # ivents_renew.join()
        answer = ""
        while answer != 'stop':
            answer = input('Нужно ли обновить? ДА/НЕТ или город: ').lower()
            if answer in ('да', "yes"):
                ivents_renew.reniew_events()
            elif answer in ('нет', "no"):
                print(shared_data.get())
                # ivents_renew.renew_event.clear()
            elif answer in ('stop', "стоп"):
                break
            else:
                ivents_renew.set_query_param({"city": answer.title(), "limit": 100})
                ivents_renew.reniew_events()

        ivents_renew = EVENTS_INFO_DYNAMIC()
        ivents_renew.start()
        ivents_renew.set_query_param({"city": answer.title()})
        ivents_renew.reniew_events()