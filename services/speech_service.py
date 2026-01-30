import requests
import httpx
import threading
from threading import Thread
from queue import Queue, Empty
from dataclasses import dataclass
from collections import deque
import numpy as np
import sys

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

    def get_audio_from_text(self, text, format='pcm16', voice='May_24000'):
        """
        Для проигрываетля нужен pcm16, для сохранения как файл лучше opus
        """
        url = f"{self.SALUTE_SYNTHESIZE_URL}?format={format}&voice={voice}"

        payload = text
        headers = {
                    'Content-Type': 'application/text',
                    'Accept': f'audio/x-{format}',
                    'Authorization': f'Bearer {self.bearer_token}'
        }

        response = self.client.request("POST", url, headers=headers, data=payload)

        audio_data = response.content
        return audio_data

    def get_text_from_audio(self, file: str, c_type='audio/mpeg'):

        url = f"{self.SALUTE_RECOGNIZE_URL}"

        with open(file, "rb") as f:
            payload = f.read()
        headers = {
                    'Content-Type': c_type,
                    'Accept': 'application/json',
                    'Authorization': f'Bearer {self.bearer_token}'
                    }

        response = self.client.request("POST", url, headers=headers, data=payload)

        text_data = response.content
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
                    raise TypeError("q_speech должен содержать AudioPacket (или None для окончания обработки)")

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
        self.save_to_disk = save_to_disk
        self.sample_rate = sample_rate # Зависит от модели голоса
        self.channels = channels

    @property
    def voice(self):
        try:
            return settings.tts_voice
        except:
            return self._voice

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
            audio_data = salut_engine.get_audio_from_text(text, self.format, self.voice)
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


if __name__ == "__main__":
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