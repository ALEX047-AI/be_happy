import requests
import httpx
import threading
from threading import Thread
from queue import Queue, Empty
from dataclasses import dataclass
from collections import deque
import numpy as np
import sys
import os

from options.config import settings


class SaluteSpeech:

    def __init__(self, use_ssml = False, ssml_prefix:str|None = None, ssml_suffix:str|None = None):
        self.SALUTE_TOKEN = settings.SALUTE_TOKEN
        self.SALUTE_TOKEN_URL = settings.SALUTE_TOKEN_URL
        self.SALUTE_RqUID = settings.SALUTE_RqUID
        self.SALUTE_SYNTHESIZE_URL = settings.SALUTE_SYNTHESIZE_URL
        self.SALUTE_RECOGNIZE_URL = settings.SALUTE_RECOGNIZE_URL

        self.use_ssml = use_ssml
        self.ssml_prefix = ssml_prefix
        self.ssml_suffix = ssml_suffix
        self._client = None
        self.token_data = self.get_auth()
        self.token = self.token_data.get('access_token')
        self.token_expires_at_int = self.token_data.get('expires_at')
        if self.token is None:
            raise RuntimeError('Не могу получить токен')

        self.headers = {
                        'Content-Type': 'application/json',
                        'accept': 'application/json'
                        }


    @property
    def client(self):
        if self._client is None:
            self._client = httpx.Client(verify=False)

        return self._client

    def close(self):
        self._client.close()

    def get_auth(self):

        payload={
                'scope': 'SALUTE_SPEECH_PERS'
        }
        headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                    'RqUID': f'{self.SALUTE_RqUID}',
                    'Authorization': f'Basic {self.SALUTE_TOKEN}'
        }

        response = self.client.request("POST", self.SALUTE_TOKEN_URL, headers=headers, data=payload)

        answer = response.json()
        self.bearer_token = answer.get('access_token')
        self.bearer_token_expires_at = answer.get('expires_at')
        # print(f'token data = {answer}')
        return answer

    def get_audio_from_text(self, text, format='pcm16', voice='May_24000', lang='ru', text_clean=True):
        """
        Для проигрываетля нужен pcm16, для сохранения как файл лучше opus
        """
        # Небольшая очистка текста, для лучшего произнесения.
        if text_clean == True and isinstance(text, str):
            text=text.replace('*', '')
        url = f"{self.SALUTE_SYNTHESIZE_URL}?format={format}&voice={voice}"
        if lang:
            c_type = 'application/ssml'
            tss_text_prefix = f"""<voice name="{voice}" lang="{lang}">"""
            tss_text_suffix = """</voice>"""
            text = f'{tss_text_prefix or ""}{text}{tss_text_suffix or ""}'
        else:
            c_type = 'application/text'

        payload = text
        headers = {
                    'Content-Type': c_type,
                    'Accept': f'audio/x-{format}',
                    'Authorization': f'Bearer {self.bearer_token}'
        }

        response = self.client.request("POST", url, headers=headers, data=payload)

        audio_data = response.content
        return audio_data

    def get_text_from_audio(self, file: str, c_type='audio/mpeg', query_param='') -> list:

        url = f"{self.SALUTE_RECOGNIZE_URL}{query_param}"

        with open(file, "rb") as f:
            payload = f.read()
        headers = {
                    'Content-Type': c_type,
                    'Accept': 'application/json',
                    'Authorization': f'Bearer {self.bearer_token}'
                    }

        response = self.client.request("POST", url, headers=headers, data=payload)

        if response.status_code == 200:
            dict_data = response.json()
            text_data = dict_data.get('result', [])
            if isinstance(text_data, list) and text_data:
                text_data = list(filter(None, text_data))
        else:
            text_data = []

        return text_data

    def get_audio_from_text0(self, text, voice='Ost_24000', format='oggopus'):
        if text == '' or text == ' ':
            print(f'пусто {text = }')
            return None
        else:
            #print(f'{text = }')
            pass

        datas = {
                "voice": voice,
                "format": format,
                }

        if self.use_ssml:
            datas["tts-ssml"] = "1"
            text = f'{self.ssml_prefix or ""}{text}{self.ssml_suffix or ""}'

        datas["text"] = text
        print(text)


        answer = requests.get(self.url, json=datas, headers=self.headers)

        return answer.content

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()


@dataclass
class AudioPacket:
    data: bytes
    fmt: str = "pcm16"
    sample_rate: int = 24000 # Качество лучше чем 8000
    channels: int = 1 # Генерация голоса всегда Моно


class SpeechPlayer(Thread):
    """
    Получаем данные аудио AudioPacket из q_in и проигрываем их непрерывно.
    start() -> запуск аудио в отдельном процессе
    pause() / resume() -> пауза/ возобновление как можно быстрее
    stop() -> стоп как можно быстрее. После stop() можно проигрывать НОВЫЕ данные.
    """

    def __init__(self, q_in: Queue, finished_item: bool = False, daemon: bool = True):
        super().__init__(daemon=daemon)
        self.q_in = q_in
        self.finished_item = finished_item

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # Если установлен то пауза
        self._buffer_lock = threading.Lock()
        self._buffers = deque()  # deque[np.ndarray[int16]] из (n_frames, channels)

        self._samplerate = None
        self._channels = None
        self._end_of_input = False

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self):
        self._stop_event.set()

    def _clean_queue(self):
        # безопасная очистка очереди
        while True:
            try:
                self.q_in.get_nowait()
            except Empty:
                break

    def _reset_player_state(self):
        # очищаем буферы/очередь и сбрасываем параметры
        with self._buffer_lock:
            self._buffers.clear()

        self._clean_queue()

        self._samplerate = None
        self._channels = None
        self._end_of_input = False

        self._stop_event.clear()
        self._pause_event.clear()

    def _append_pcm(self, pcm_bytes: bytes, sample_rate: int, channels: int):
        if self._samplerate is None:
            self._samplerate = sample_rate
            self._channels = channels
        elif self._samplerate != sample_rate or self._channels != channels:
            raise ValueError(
                f"Кусочки должны быть одного формата ГЦ/Каналы"
                f"Ожидаем {self._samplerate} Гц /{self._channels} каналов, было получено {sample_rate} Гц/{channels} каналов."
            )

        # pcm16 -> длина должна быть кратна 2
        if len(pcm_bytes) % 2 != 0:
            pcm_bytes = pcm_bytes[:-1]

        audio = np.frombuffer(pcm_bytes, dtype=np.int16)
        if channels > 1:
            audio = audio.reshape(-1, channels)
        else:
            audio = audio.reshape(-1, 1)

        with self._buffer_lock:
            self._buffers.append(audio)

    def run(self):
        import sounddevice as sd

        while True:
            # На старте каждой сессии сбрасываем end_of_input (важно!)
            self._end_of_input = False

            # Ждем первый пакет и определяем samplerate/channels
            while not self._stop_event.is_set():
                try:
                    pkt = self.q_in.get(timeout=0.1)
                except Empty:
                    continue

                if self.finished_item and pkt is None:
                    # Сигнал конца текущей генерации, но еще не начали проигрывать.
                    # сброс и ждем следующий поток аудио.
                    self._end_of_input = True
                    break

                if not isinstance(pkt, AudioPacket):
                    raise TypeError("q_speech должен содержать AudioPacket (или None для завершения обработки)")

                if pkt.fmt == "pcm16":
                    self._append_pcm(pkt.data, pkt.sample_rate, pkt.channels)
                    break
                else:
                    raise ValueError(f"Такой формат не поддерживается: {pkt.fmt}")

            # Если нажали stop пока ждали первый пакет — чистим и снова ждем дальше
            if self._stop_event.is_set():
                self._reset_player_state()
                continue

            # Если ничего не установилось (например пришел None) — сброс и ждать новую сессию
            if self._samplerate is None:
                self._reset_player_state()
                continue

            current = None
            pos = 0

            def callback(outdata, frames, time, status):
                nonlocal current, pos
                outdata[:] = 0

                if self._stop_event.is_set() or self._pause_event.is_set():
                    return

                filled = 0
                while filled < frames and not self._stop_event.is_set() and not self._pause_event.is_set():
                    if current is None:
                        with self._buffer_lock:
                            current = self._buffers.popleft() if self._buffers else None
                        pos = 0
                        if current is None:
                            break

                    remaining = current.shape[0] - pos
                    if remaining <= 0:
                        current = None
                        pos = 0
                        continue

                    take = min(frames - filled, remaining)
                    outdata[filled:filled + take, :] = current[pos:pos + take, :]
                    pos += take
                    filled += take

            # Основной цикль проигрывателя: ждем пока не закончаться данные или не поступи команда стоп
            with sd.OutputStream(
                samplerate=self._samplerate,
                channels=self._channels,
                dtype="int16",  # только 16 бит.
                callback=callback,
                blocksize=0,    # автовыбор
            ):
                while not self._stop_event.is_set():
                    try:
                        pkt = self.q_in.get(timeout=0.1)
                    except Empty:
                        pkt = None

                    if pkt is None:
                        # проверяем конец или таймаут
                        if self.finished_item and self._end_of_input:
                            # проверка
                            with self._buffer_lock:
                                drained = (len(self._buffers) == 0)
                            if drained and current is None:
                                break
                        continue

                    if self.finished_item and pkt is None:
                        self._end_of_input = True
                        continue

                    if not isinstance(pkt, AudioPacket):
                        raise TypeError("q_speech должен содержать AudioPacket (или None для окончания обработки)")

                    if pkt.fmt == "pcm16":
                        self._append_pcm(pkt.data, pkt.sample_rate, pkt.channels)
                    else:
                        raise ValueError(f"Не поддерживаемый формат: {pkt.fmt}")

            # ВАЖНО: после выхода (стоп/конец) нужно сбросить состояние,
            # чтобы можно было проигрывать новые данные потом.
            self._reset_player_state()


class TTS_Stream(Thread):
    def __init__(self, q_in: Queue, q_out: Queue, daemon=True, finished_item=False,
                 voice='May_24000', save_to_disk=False,
                 sample_rate=24000, channels=1):
        super().__init__(daemon=daemon)
        self.q_in = q_in
        self.q_out = q_out
        self._buffer_lock = threading.Lock()
        # Если установлен то нет помещаем последний сгенерированный фрагмент в очередь
        # Это нужно для того, чтобы при отмене произношения последний попавший на генерацию блок не произносился
        # и не попадал в очередь плеера.
        self._text_to_queue_event_pause = threading.Event()
        self._text_to_queue_event_pause.clear() # устанавливаем в значение отправка в очередь

        self.finished_item = finished_item
        self.format = 'pcm16'
        self._voice = voice
        self._lang_chat = 'ru'
        self.save_to_disk = save_to_disk
        self.sample_rate = sample_rate # Зависит от модели голоса
        self.channels = channels

    @property
    def voice(self):
        try:
            return settings.tts_voice
        except:
            return self._voice

    @property
    def lang_chat(self):
        try:
            return settings.app_options.LANG_CHAT
            # settings.app_options.LANG_UI
        except:
            return self._lang_chat

    def _clean_queue(self):
        # безопасная очистка очереди
        while True:
            try:
                # with self._buffer_lock:
                self.q_in.get_nowait()
            except Empty:
                break

    def resume_queue(self):
        self._text_to_queue_event_pause.clear()
    def stop_queue(self):
        self._text_to_queue_event_pause.set()
        self._clean_queue()

    def run(self):
        salut_engine = SaluteSpeech()
        count = 0
        while True:
            with self._buffer_lock:
                text = self.q_in.get()
            if self.finished_item and text is None:
                print("Получен сигнал завершения генерации")
                # Если добавить, то больше не ожидается продолжения генераций. Не для приложения.
                self.q_out.put(None)
                break

            count += 1
            print(f"чанк # {count} -> TTS", flush=True)
            audio_data = salut_engine.get_audio_from_text(text, self.format, self.voice, self.lang_chat)
            try:
                if not self._text_to_queue_event_pause.is_set():
                    pkt = AudioPacket(
                        data=audio_data,
                        fmt="pcm16",
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                    )
                    self.q_out.put(pkt)
                    print(f"аудио # {count} сгенерировано", flush=True)
                else:
                    print(f"аудио # {count} сгенерировано, но отменено", flush=True)
            finally:
                self._text_to_queue_event_pause.clear()

            if self.save_to_disk:
                ext = "pcm" if pkt.fmt == "pcm16" else "raw"
                with open(f"out__{count}.{ext}", "wb") as f:
                    f.write(audio_data)

@dataclass
class ASRJob:
    """Задание на распознавание речи."""
    file: str
    # c_type: str = "audio/wav"
    c_type: str = "audio/x-pcm;bit=16;rate=16000"
    query_param: str = "?language=ru-RU&sample_rate=16000&channels_count=1"
    cleanup: bool = True


@dataclass
class ASRResult:
    """Результат распознавания речи."""
    texts: list[str]
    job: ASRJob
    error: str | None = None


class ASR_Stream(Thread):
    """Фоновый worker: берёт ASRJob из q_in, кладёт ASRResult в q_out."""

    def __init__(self, q_in: Queue, q_out: Queue, daemon: bool = True, finished_item: bool = False):
        super().__init__(daemon=daemon)
        self.q_in = q_in
        self.q_out = q_out
        self.finished_item = finished_item
        self._buffer_lock = threading.Lock()

    def _clean_queue(self):
        while True:
            try:
                self.q_in.get_nowait()
            except Empty:
                break

    def stop_queue(self):
        # очистить очередь ожидания распознавания
        self._clean_queue()

    def run(self):
        salut_engine = None
        try:
            salut_engine = SaluteSpeech()
        except Exception as e:
            # Если не получилось создать движок — дальше смысла нет.
            self.q_out.put(ASRResult(texts=[], job=ASRJob(file=""), error=repr(e)))
            return

        while True:
            with self._buffer_lock:
                job = self.q_in.get()

            if job is None:
                if self.finished_item:
                    self.q_out.put(None)
                    break
                continue

            # Позволяем короткий формат: просто путь к файлу
            if isinstance(job, str):
                job = ASRJob(file=job)

            if not isinstance(job, ASRJob):
                self.q_out.put(ASRResult(texts=[], job=ASRJob(file=""), error="ASR_Stream: unsupported job type"))
                continue

            try:
                texts = salut_engine.get_text_from_audio(job.file, c_type=job.c_type, query_param=job.query_param)
                res = ASRResult(texts=texts or [], job=job, error=None)
            except Exception as e:
                res = ASRResult(texts=[], job=job, error=repr(e))
            finally:
                if job.cleanup:
                    try:
                        os.remove(job.file)
                    except Exception:
                        pass

            self.q_out.put(res)





if __name__ == "__main__":

    # Проверка ASR
    salut_engine = SaluteSpeech()
    text_data = salut_engine.get_text_from_audio('left_mono.wav', c_type='audio/x-pcm;bit=16;rate=8000', query_param='?language=ru-RU&sample_rate=8000&channels_count=1')
    print(text_data)

    sys.exit()

    # Проверка TTS
    q_text = Queue()
    q_speech = Queue()

    text_list = [
        "Ольга, привет! ",
        "Очень хорошо, что ты здесь. ",
        "Помни, путь к лучшему состоянию может казаться долгим ",
        # "но, как говорится, дорогу осилит идущий. ",
        # "Я буду рядом, чтобы поддержать тебя на этом пути, ",
        # "и вместе мы сможем сделать его немного легче и приятнее.",
        # "Я очень надеюсь, что ты сможешь почувствовать радость и счастье.",
        # "Ты важна. Если тебе захочется поделиться чем-то, я здесь, чтобы выслушать."
    ]

    player = SpeechPlayer(q_in=q_speech, finished_item=True, daemon=True)
    player.start()

    task = TTS_Stream(q_in=q_text, q_out=q_speech, daemon=False,
                        finished_item=True, save_to_disk=False,
                        sample_rate=24000, channels=1
            )
    task.start()

    for num, item in enumerate(text_list, start=1):
        q_text.put(item)
        print(f"{num} добавлен")
    q_text.put(None)

    # Управление плеером.
    while True:
        command = input(f'Выберите действие s - Stop, p - Pause, r - Resume:, e - Exit: ')
        if command.lower() == 's':
            player.stop()
        elif command.lower() == 'p':
            player.pause()
        elif command.lower() == 'r':
            player.resume()
        elif command.lower() == 'e':
            sys.exit()