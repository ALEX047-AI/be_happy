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

from articles import main_articles, support_phrases
from options.config import settings


from queue import Queue

class LLM_IO:

    def __init__(self, human_profile, model_source="openrouter", ai_intro: str=None):

        self.last_llm_answer = ""
        self.model_source = model_source
        self.human_profile = human_profile
        self.history = []  # история чата с ЛЛМ
        self.ai_intro = ai_intro
        if self.ai_intro is not None and isinstance(self.ai_intro, str):
            self.history.append(AIMessage(content=self.ai_intro))

        self.text_stream_last_queue = Queue()
        self._text_to_queue_event_pause = threading.Event()  # Если снят то отправляем в очередь
        self._text_to_queue_event_pause.clear() # устанавливаем в значение отправка в очередь

        if self.model_source == "mistral":
            ...
            llm = ChatMistralAI(
            api_key=settings.MISTRAL_API_KEY,
            base_url=settings.MISTRAL_BASE_URL,
                model=settings.MISTRAL_MODEL,
                temperature=0,
            )
        else:
            llm = ChatOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                #   http_client=httpx.Client(proxy="socks5://127.0.0.1:8888"),
                model=settings.OPENROUTER_MODEL #"google/gemma-3-27b-it:free",

            #   model="mistralai/mistral-7b-instruct:free"
            #   model="mistralai/mistral-small-3.2-24b-instruct:free"
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

        retriever = BM25Retriever.from_documents(knowledge_store, k=settings.retriever_docs_number)

        # Профиль человека теперь в system
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
            'Ты ассистент эмоциональной поддержки, не человек. Ты женщина.'
            'Не говори от своего имени. что вы что-то может вместе с пользователем. эмоциональную поддержку могут оказать другие люди, которых упомянул пользователь. '
            'Но если по контексту подходит напомни, что у человека есть близкие ему люди которые упомянул сам человек и они могут помочь человеку, сделать что-то вместе. '
            'Ты мягко, бережно и уважительно общаешься с пользователями, которые могут находиться в сложном эмоциональном состоянии. '
            'Тебе передаётся контекст ответа — используй его как основу, допускается перефразирование и использование синонимов. '
            'Вопросы пользователю не задавай, дополнительных советов вне переданного контекста не давай. '
            'Общайся спокойно, поддерживающе и с заботой, избегая резких формулировок и давления.'
            "Используй персонализированный ответ на основе данных о человеке.\n\n"
            "ДАННЫЕ О ЧЕЛОВЕКЕ:\n{human_profile}\n\n"
            "Context: {context}\n"
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
            max_tokens=settings.LLM_TRIMMER_MAX_TOKENS,
            # start_on="human",
            end_on="human",
            include_system=True,
            allow_partial=False,
        )

        def debug_print(x, label=""):
            if settings.LLM_DEBUG:
                print(f"\n--- {label} ({type(x)}) ---\n{x}\n")
            return x

        prnt_prompt = RunnableLambda(lambda x: debug_print(x, "AFTER prompt"))
        prnt_trimmed = RunnableLambda(lambda x: debug_print(x, "AFTER trimmer"))

        self.chain = (
            RunnableParallel(
                context=(lambda x: x["question"]) | retriever | self.format_documents,
                question=lambda x: x["question"],
                history=lambda x: x["history"],
                human_profile=lambda x: x["human_profile"],
            )
            | prompt
            | prnt_prompt
            | self.trimmer
            | prnt_msg
            | llm
            | StrOutputParser()
        )

        """ chain_no_rag = RunnableParallel(
            question=lambda data: data
        ) | prompt_no_rag | llm | StrOutputParser()
        result = chain_no_rag.invoke("График")
        print(result) """

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


    def print_messages(self, msgs):
        if settings.LLM_DEBUG:
            print("\n=== TRIMMED MESSAGES ===")
            for i, m in enumerate(msgs):
                # BaseMessage может быть .type .content; system/human/ai/tool
                print(f"{i:02d} | {m.type}: {m.content!r}")
            print("========================\n")
        return msgs

    def get_frase_from_llm(self, question="дай мне совет"):
        if not settings.USE_LLM:
            return random.choice(support_phrases)

        self.history.append(HumanMessage(content=question))
        result = self.chain.invoke({
            "question": question,
            "history": self.history,
            "human_profile": self._profile_text(),
        })
        self.history.append(AIMessage(content=result))
        return result

    def get_frase_from_llm_stream(self, question="дай мне совет"):
        self.history.append(HumanMessage(content=question))
        self.last_llm_answer = ""
        self._text_to_queue_event_pause.clear()

        if settings.USE_LLM:
            count = -1
            msg_chunk_packed = ""
            msg_chunk_list = []
            try:
                for msg_chunk in self.chain.stream({
                    "question": question,
                    "history": self.history,
                    "human_profile": self._profile_text(),
                }):
                    self.last_llm_answer += msg_chunk
                    if isinstance(msg_chunk, str):
                        msg_chunk_list.append(msg_chunk)
                        if msg_chunk.endswith(('\n', '.')):
                            msg_chunk_packed = ''.join(msg_chunk_list)
                            msg_chunk_packed = msg_chunk_packed.strip(' \n')
                            if msg_chunk_packed:
                                count += 1
                                if not self._text_to_queue_event_pause.is_set():
                                    self.text_stream_last_queue.put(msg_chunk_packed)
                                if settings.LLM_DEBUG:
                                    print(f'{count = }, {msg_chunk_packed =  }')
                            msg_chunk_list = []
                            msg_chunk_packed = ""
                    # print(f'chunk № {count}, {msg_chunk = }')
                    yield msg_chunk
            finally:
                self._text_to_queue_event_pause.clear()

            if settings.LLM_DEBUG:
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

    question = "дай мне совет"
    llm_item = LLM_IO(human_profile)
    # print(f'qsize start = {llm_item.text_stream_last_queue.qsize()}')
    # from time import sleep
    # sleep(2)
    for msg_chunk in llm_item.get_frase_from_llm_stream(question):
        print(msg_chunk, end='', flush=True)

    print(f'\n________________________________________')
    print(llm_item.print_messages(llm_item.history))

    # result = chain.invoke({"question": question, "history": history})
    # print(result)