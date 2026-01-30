from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, trim_messages, AIMessage
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnableLambda
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

import random
import threading
import os
from datetime import datetime

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from articles import main_articles, support_phrases
from options.config import settings


from queue import Queue

from services.city_events import SharedData #format_events
from data.models.data_for_joblib import texts_pos, texts_neg
from services.city_events import EVENTS_INFO_DYNAMIC, SharedData

# Для определения намерения пользователя узнать куда можно сходить
# используем joblib и микросет образцов

_EVENT_INTENT_MODEL = None


def default_events_intent_train_data(texts_pos, texts_neg):
    # 1 = пользователь хочет сходить на мероприяте; 0 = не про мероприятия
    """ texts_pos = [
        "где я могу проветриться",
        "куда сходить сегодня",
        "куда можно сходить",
        "куда пойти вечером",
        "что поделать в выходные",
        "чем заняться",
        "посоветуй мероприятие",
        "есть концерты на неделе",
        "хочу на выставку",
        "хочу куда-нибудь выбраться",
        "покажи афишу",
        "есть экскурсии",
        "хочу развлечься",
        "посоветуй досуг",
    ]
    texts_neg = [
        "мне грустно",
        "мне тревожно",
        "как справиться с паникой",
        "помоги составить план дня",
        "я устал и не могу уснуть",
        "почему мне плохо",
        "как перестать переживать",
        "помоги с дыханием",
        "у меня апатия",
        "мне нужна поддержка",
    ] """
    texts = texts_pos + texts_neg
    labels = [1] * len(texts_pos) + [0] * len(texts_neg)
    return texts, labels


def train_events_intent_model():

    texts, labels = default_events_intent_train_data(texts_pos, texts_neg)

    clf = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
        ("lr", LogisticRegression(max_iter=400)),
    ])
    clf.fit(texts, labels)
    return clf


def load_or_train_events_intent_model(model_path: str):
    global _EVENT_INTENT_MODEL

    if _EVENT_INTENT_MODEL is not None:
        return _EVENT_INTENT_MODEL

    try:
        if os.path.exists(model_path):
            _EVENT_INTENT_MODEL = joblib.load(model_path)
            return _EVENT_INTENT_MODEL
    except Exception:
        # если не загрузили то нужна тренировка
        pass

    model = train_events_intent_model()

    try:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
    except Exception:
        # при ошибке сохранения далее все равно возвращаем модель.
        pass

    _EVENT_INTENT_MODEL = model
    return _EVENT_INTENT_MODEL


class LLM_IO:

    def __init__(self, human_profile, model_source="openrouter", ai_intro: str=None, shared_data: SharedData = None):

        self.last_llm_answer = ""
        self.model_source = model_source
        self.human_profile = human_profile
        self._llm_gender = self.llm_gender
        self.history = []  # история чата с ЛЛМ
        self.ai_intro = ai_intro

        self.proba_limit = settings.PROBA_LIMIT
        self.EVENT_LIMIT_SEND_TO_LLM = settings.EVENT_LIMIT_SEND_TO_LLM
        self.LLM_DEBUG = settings.LLM_DEBUG
        self.LLM_TRIMMER_MAX_TOKENS = settings.LLM_TRIMMER_MAX_TOKENS

        self.MISTRAL_API_KEY = settings.MISTRAL_API_KEY
        self.MISTRAL_BASE_URL = settings.MISTRAL_BASE_URL
        self.MISTRAL_MODEL = settings.MISTRAL_MODEL
        self.MISTRAL_TEMPERATURE = settings.MISTRAL_TEMPERATURE

        self.OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
        self.OPENROUTER_BASE_URL = settings.OPENROUTER_BASE_URL
        self.OPENROUTER_MODEL = settings.OPENROUTER_MODEL
        self.OPENROUTER_TEMPERATURE = settings.OPENROUTER_TEMPERATURE

        self.EVENT_LIMIT_SEND_TO_LLM = settings.EVENT_LIMIT_SEND_TO_LLM
        self.retriever_docs_number = settings.retriever_docs_number
        self.DATA = settings.DATA
        self.USE_LLM = settings.USE_LLM

        if self.ai_intro is not None and isinstance(self.ai_intro, str):
            self.history.append(AIMessage(content=self.ai_intro))

        # Загружаем события
        self._events_doc = []  # список событий (обновляется отдельно)
        self._events_model_path = os.path.join(self.DATA, "models", "events_intent.joblib")
        self._events_intent_model = load_or_train_events_intent_model(self._events_model_path)

        # это обновляемые извен события. данный объект является общим с другими классами.
        self._shared_data = shared_data


        self.text_stream_last_queue = Queue()
        self._text_to_queue_event_pause = threading.Event()  # Если снят то отправляем в очередь
        self._text_to_queue_event_pause.clear() # устанавливаем в значение отправка в очередь

        if self.model_source == "mistral":
            llm_service = dict(
                api_key=self.MISTRAL_API_KEY,
                base_url=self.MISTRAL_BASE_URL,
                model=self.MISTRAL_MODEL,
                temperature=self.MISTRAL_TEMPERATURE,
            )
        else:
            llm_service = dict(
                api_key=self.OPENROUTER_API_KEY,
                base_url=self.OPENROUTER_BASE_URL,
                model=self.OPENROUTER_MODEL,
                temperature=self.OPENROUTER_TEMPERATURE,
            )
            """ llm = ChatOpenAI(
                api_key=self.OPENROUTER_API_KEY,
                base_url=self.OPENROUTER_BASE_URL,
                model=self.OPENROUTER_MODEL,
                temperature=self.OPENROUTER_TEMPERATURE,
            ) """
                #   http_client=httpx.Client(proxy="socks5://127.0.0.1:8888"),

            #"google/gemma-3-27b-it:free",
            #   model="mistralai/mistral-7b-instruct:free"
            #   model="mistralai/mistral-small-3.2-24b-instruct:free"


        # llm = ChatMistralAI(
        llm = ChatOpenAI(
            **llm_service
        )

        """knowledge_store = [
            Document(page_content="Спасибо, что делишься со мной своими мыслями и чувствами. Я очень ценю твое доверие"),
            # ...
        ]"""


        self.profile = ', '.join([f'{key} - {value}' for key, value in self.human_profile.items() if value is not None and value != ""])
        self.request = f'Данные обо мне: {self.profile}'
        print(f'{self.request = }')

        # self.history = [HumanMessage(content=self.request)]

        knowledge_store = [
            Document(page_content=article) for article in main_articles
        ]

        retriever = BM25Retriever.from_documents(knowledge_store, k=self.retriever_docs_number)

        # Профиль человека теперь в system
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
            'Ты ассистент эмоциональной поддержки, не человек. Ты {llm_gender} '
            'Не говори от своего имени. что вы что-то может вместе с пользователем. эмоциональную поддержку могут оказать другие люди, которых упомянул пользователь. '
            'Но если по контексту подходит напомни, что у человека есть близкие ему люди которые упомянул сам человек и они могут помочь человеку, сделать что-то вместе. '
            'Ты мягко, бережно и уважительно общаешься с пользователями, которые могут находиться в сложном эмоциональном состоянии. '
            'Тебе передаётся контекст ответа — используй его как основу, допускается перефразирование и использование синонимов. '
            'Вопросы пользователю не задавай, дополнительных советов вне переданного контекста не давай. '
            'Общайся спокойно, поддерживающе и с заботой, избегая резких формулировок и давления. '
            'События/мероприятия предлагай ТОЛЬКО если пользователь прямо просит или явно намекает, что хочет куда-то сходить/развлечься и не более пяти событий.'
            'Events содержит информацию в формате json'
            "Используй персонализированный ответ на основе данных о человеке.\n\n"
            "ДАННЫЕ О ЧЕЛОВЕКЕ:\n{human_profile}\n\n"
            "Context: {context}\n"
            "Events: {events_context}\n"
            "Question: {question}"
            )),
            MessagesPlaceholder("history"),
        ])

        #    "human_profile: {human_profile}"
        prompt_no_rag = ChatPromptTemplate.from_messages([
            ("system", (
                'Ты голосовой ассистент, который обрабатывает информация услышанную от пользователя,'
            "\nQuestion: {question}"
                )
            )
        ])

        prnt_msg = RunnableLambda(self.print_messages)

        self.trimmer = trim_messages(
            strategy="last",
            token_counter=len,
            max_tokens=self.LLM_TRIMMER_MAX_TOKENS,
            # start_on="human",
            end_on="human",
            include_system=True,
            allow_partial=False,
        )

        def debug_print(x, label=""):
            if self.LLM_DEBUG:
                print(f"\n--- {label} ({type(x)}) ---\n{x}\n")
            return x

        prnt_prompt = RunnableLambda(lambda x: debug_print(x, "AFTER prompt"))
        prnt_trimmed = RunnableLambda(lambda x: debug_print(x, "AFTER trimmer"))

        self.chain = (
            RunnableParallel(
                context=(lambda x: x["question"]) | retriever | self.format_documents,
                events_context=lambda x: self.events_to_context(x["question"], x["history"]),
                question=lambda x: x["question"],
                history=lambda x: x["history"],
                llm_gender=lambda x: x["llm_gender"],
                human_profile=lambda x: x["human_profile"],
            )
            | prompt
            | prnt_prompt
            | self.trimmer
            | prnt_msg
            | llm
            | StrOutputParser()
        )

        # llm_gender=lambda x: x["llm_gender"],
        """ chain_no_rag = RunnableParallel(
            question=lambda data: data
        ) | prompt_no_rag | llm | StrOutputParser()
        result = chain_no_rag.invoke("График")
        print(result) """

    @property
    def llm_gender(self):
        return settings.llm_gender

    @property
    def get_last_events_data(self):
        """Если используется общее хранилище SharedData, то перед выдаче обновляем данные"""
        if self._shared_data is not None and isinstance(self._shared_data, SharedData):
            self._events_doc = self._shared_data.get()
        return self._events_doc

    def pause_last_llm_text_stream_to_queue(self):
        self._text_to_queue_event_pause.set()

    def update_profile(self, human_profile: dict):
        """Обновить профиль в уже созданном классе без потери истории"""
        self.human_profile = human_profile

    def clear_history(self):
        """Обнулить историю"""
        self.history = []
        if self.ai_intro is not None and isinstance(self.ai_intro, str):
            self.history.append(AIMessage(content=self.ai_intro))

    def _profile_text(self) -> str:
        profile = ", ".join(
            f"{k} - {v}"
            for k, v in self.human_profile.items()
            if v is not None and str(v).strip() != ""
        )
        return profile if profile else "(профиль не заполнен)"

    def format_documents(self, documents: list[Document]):
        return "\n\n".join(doc.page_content for doc in documents)


    # Обработка событий
    def update_events(self, events_doc: list[dict]):
        """Обновить список событий (динамически)
        Используется только если не используется SharedData"""
        self._events_doc = events_doc or []

    def want_events_ml(self, question: str) -> bool:
        """определяем хочет ли пользователь идеи/мероприятия"""

        q = (question or "").strip()
        if not q:
            return False

        proba = self._events_intent_model.predict_proba([q])[0][1]
        print(f'want_events_ml {proba = }')
        return proba >= self.proba_limit

    def events_to_context(self, question: str, history: list, limit = None) -> str:
        """Возвращаем events_context только когда это действительно нужно"""

        limit = limit or self.EVENT_LIMIT_SEND_TO_LLM

        if not self.get_last_events_data:
            return ""

        try:
            if not self.want_events_ml(question):
                return ""
        except Exception:
            return ""

        # events_text1 = format_events(self.get_last_events_data, limit=limit)
        events_text = self.get_last_events_data
        if not events_text:
            return ""

        print(f'events_to_context yes')
        return (
            "EVENTS (используй только если пользователь просит/намекает на досуг/мероприятия):\n"
            f"{events_text}"
        )

    def print_messages(self, msgs):
        if self.LLM_DEBUG:
            print("\n=== TRIMMED MESSAGES ===")
            for i, m in enumerate(msgs):
                # BaseMessage может быть .type .content; system/human/ai/tool
                print(f"{i:02d} | {m.type}: {m.content!r}")
            print("========================\n")
        return msgs

    def get_frase_from_llm(self, question="дай мне совет"):
        if not self.USE_LLM:
            return random.choice(support_phrases)

        self.history.append(HumanMessage(content=question))
        result = self.chain.invoke({
            "question": question,
            "history": self.history,
            "human_profile": self._profile_text(),
            "llm_gender": self.llm_gender
        })
        self.history.append(AIMessage(content=result))
        return result

    def get_frase_from_llm_stream(self, question="дай мне совет"):
        self.history.append(HumanMessage(content=question))
        self.last_llm_answer = ""
        self._text_to_queue_event_pause.clear()

        if self.USE_LLM:
            count = -1
            msg_chunk_packed = ""
            msg_chunk_list = []
            try:
                for msg_chunk in self.chain.stream({
                    "question": question,
                    "history": self.history,
                    "human_profile": self._profile_text(),
                    "llm_gender": self.llm_gender,
                }):
                    self.last_llm_answer += msg_chunk
                    if isinstance(msg_chunk, str):
                        msg_chunk_list.append(msg_chunk)
                        # print(msg_chunk) # вывести текущий чанк
                        if msg_chunk.endswith(('\n', '.', '?', '!')):
                            msg_chunk_packed = ''.join(msg_chunk_list)
                            msg_chunk_packed = msg_chunk_packed.strip(' \n')
                            if msg_chunk_packed:
                                count += 1
                                if not self._text_to_queue_event_pause.is_set():
                                    self.text_stream_last_queue.put(msg_chunk_packed)
                                if self.LLM_DEBUG:
                                    print(f'{count = }, {msg_chunk_packed =  }') #вывести текущее предложение
                            msg_chunk_list = []
                            msg_chunk_packed = ""
                    # print(f'chunk № {count}, {msg_chunk = }')
                    yield msg_chunk
            finally:
                self._text_to_queue_event_pause.clear()

            if self.LLM_DEBUG:
                print(f'{count = }, qsize = {self.text_stream_last_queue.qsize()}')


        else:
            chunk = random.choice(support_phrases)
            self.last_llm_answer = chunk
            yield chunk

        self.history.append(AIMessage(content=self.last_llm_answer))


if __name__ == '__main__':
    human_profile = {
            'Имя': 'Оля',
            "Пол": "",
            "Город": "Екатеринбург",
            'Дата рождения': '12.12.2000',
            'Семейное положение': 'за мужем',
            'Родители': 'да', # мама/папа
            'Дети': 'да', # количество детей
            'Друзья': 'да',
            'Комментарий': 'За мужем, есть друзья и дети.'

        }

    """ profile = ', '.join([f'{key} - {value}' for key, value in human_profile.items()])
    question = "дай мне совет"
    request = f'Данные обо мне: {profile}'
    print(f'{request = }')
    """

    question = "дай мне совет куда можно сходить"
    shared_data = SharedData()
    llm_item = LLM_IO(human_profile, shared_data=shared_data)
    ivents_renew = EVENTS_INFO_DYNAMIC(shared_data)
    ivents_renew.start()
    from time import sleep
    sleep(4)
    print(question)
    _user_city = human_profile.get('Город')
    if _user_city:
        if isinstance(_user_city, str):
            ivents_renew.set_query_param({"city": _user_city.title()}, renew=True)

    """     # добавляем события
        llm_item.update_events(events_doc)
    """
    # print(f'qsize start = {llm_item.text_stream_last_queue.qsize()}')
    # from time import sleep
    # sleep(2)
    for msg_chunk in llm_item.get_frase_from_llm_stream(question):
        print(msg_chunk, end='', flush=True)

    print(f'\n________________________________________')
    print(llm_item.print_messages(llm_item.history))

    # result = chain.invoke({"question": question, "history": history})
    # print(result)