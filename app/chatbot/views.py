from django.shortcuts import render
from django.http import JsonResponse
from decouple import config
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.agents import Tool
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.engine import make_url
import psycopg2
import os


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

connection_string = os.getenv("DB_CONNECTION_STRING")
db_name = config("DB_NAME", "")
conn = psycopg2.connect(connection_string)
conn.autocommit = True
url = make_url(connection_string)
vector_store = PGVectorStore.from_params(
    database=db_name,
    host=url.host,
    password=url.password,
    port=url.port,
    user=url.username,
    table_name="LLMFutureOfAI",
    embed_dim=1536,
)

index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
query_engine = index.as_query_engine()

# create langchain tool
tools = [
    Tool(
        name="Article AI",
        func=lambda q: str(index.as_query_engine().query(q)),
        description="""
            Useful only when there are questions about specific knowledge.
            This is not useful for general knowledge
        """,
        return_direct=True,
    ),
]

memory = ConversationBufferWindowMemory(memory_key="chat_history", k=6)

llm = ChatOpenAI(temperature=0, api_key=OPENAI_API_KEY, model="gpt-4")
agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent="conversational-react-description",
    memory=memory,
    verbose=True,
    handle_parsing_errors=False,
)


# @traceable
def ask_openai_rag(message):
    answer = agent_executor.run(input=message)
    return answer


# @traceable
def chatbot(request):
    if request.method == "POST":
        message = request.POST.get("message")
        response = ask_openai_rag(message)
        return JsonResponse({"message": message, "response": response})
    return render(request, "chatbot.html")
