from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
#from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from articles import main_articles
from options.config import settings

API_KEY = settings.API_KEY
BASE_URL = settings.BASE_URL


llm = ChatOpenAI(
  api_key=API_KEY,
  base_url=BASE_URL,
#   http_client=httpx.Client(proxy="socks5://127.0.0.1:8888"),
  model="google/gemma-3-27b-it:free"

)
#   model="mistralai/mistral-7b-instruct:free"
#   model="mistralai/mistral-small-3.2-24b-instruct:free"

"""knowledge_store = [
    Document(page_content="Спасибо, что делишься со мной своими мыслями и чувствами. Я очень ценю твое доверие"),
    # ...
]"""

knowledge_store = [
    Document(page_content=article) for article in main_articles
]
retriever = BM25Retriever.from_documents(knowledge_store)


def format_documents(documents: list[Document]):
    return "\n\n".join(doc.page_content for doc in documents)


prompt = ChatPromptTemplate.from_messages([
    ("system", (
       'Ты ассистент эмоциональной поддержки, не человек. '
       'Не говори от своего имени. что вы что-то может вместе с пользователем. эмоциональную поддержку могут оказать другие люди, которых упомянул пользователь. '
       'Но если по контексту подходит напомни, что у человека есть близкие ему люди которые упомянул сам человек и они могут помочь человеку, сделать что-то вместе. '
       'Ты мягко, бережно и уважительно общаешься с пользователями, которые могут находиться в сложном эмоциональном состоянии. '
       'Используй персонализированный ответ на основе данных о человеке. '
       'Тебе передаётся контекст ответа — используй его как основу, допускается перефразирование и использование синонимов. '
       'Вопросы пользователю не задавай, дополнительных советов вне переданного контекста не давай. '
       'Общайся спокойно, поддерживающе и с заботой, избегая резких формулировок и давления.'
       "Context: {context} \nQuestion: {question}"
        ),
    ),
    MessagesPlaceholder("history")
])
    #    "human_profile: {human_profile}"
prompt_no_rag = ChatPromptTemplate.from_messages([
    ("system", (
        'Ты голосовой ассистент, который обрабатывает информация услышанную от пользователя,'
       "\nQuestion: {question}"
        )
    )
])

human_profile = {
    'name': 'Оля',
    'date_of_birth': '12.12.2000',
    'description': 'За мужем, есть друзья и дети.'

}
# llm = ChatMistralAI(
#     model="open-mistral-7b",
#     temperature=0,
# )

""" chain_no_rag = RunnableParallel(
    question=lambda data: data
) | prompt_no_rag | llm | StrOutputParser()
result = chain_no_rag.invoke("График")
print(result) """

chain = RunnableParallel(
        context=(lambda x: x["question"]) | retriever | format_documents,        question=lambda x: x["question"],
        history=lambda x: x['history']
    ) | prompt | llm | StrOutputParser()

if __name__ == '__main__':
    profile = ', '.join([f'{key} - {value}' for key, value in human_profile.items()])
    question = "дай мне совет"
    request = f'Данные обо мне: {profile}'
    print(f'{request = }')
    history = [HumanMessage(content=request)]
    result = chain.invoke({"question": question, "history": history})
    print(result)