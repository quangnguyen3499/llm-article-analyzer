from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decouple import config
import logging
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.agents import Tool
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.engine import make_url
import psycopg2
import os
import time
import requests
from .ollama import OllamaLLM
from .models import CareerProfile


# Lazy-initialized globals
_agent_executor = None
_index = None
_vector_store = None
_embedding_client = None

SUPPORTED_PROFILE_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
MAX_PROFILE_SIZE = 5 * 1024 * 1024


def _extract_profile_text(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    if suffix not in SUPPORTED_PROFILE_SUFFIXES:
        raise ValueError("Upload a .txt, .md, .pdf, or .docx file.")
    if uploaded_file.size > MAX_PROFILE_SIZE:
        raise ValueError("The profile file must be 5 MB or smaller.")

    if suffix in {".txt", ".md"}:
        return uploaded_file.read().decode("utf-8", errors="replace").strip()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(uploaded_file).pages).strip()

    from docx import Document

    document = Document(uploaded_file)
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()


def _career_context():
    profile = CareerProfile.objects.first()
    if profile is None or not profile.content.strip():
        return ""
    return (
        "You are my personal technology career agent. Use the profile below as "
        "the source of truth about my experience. Give practical, honest advice "
        "for Python, data, and IT jobs. Do not invent qualifications.\n\n"
        f"MY PROFILE ({profile.source_name}):\n{profile.content[:16000]}\n\n"
    )


def _init_agent():
    global _agent_executor, _index, _vector_store
    if _agent_executor is not None:
        return

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    llm_backend = os.getenv("LLM_BACKEND", "OLLAMA").upper()
    emb_backend = os.getenv("EMBEDDING_BACKEND", "OLLAMA").upper()
    rag_enabled = os.getenv("RAG_ENABLED", "1").lower() in {"1", "true", "yes"}
    connection_string = os.getenv("DB_CONNECTION_STRING")
    db_name = config("DB_NAME", "")

    # simple retry/backoff helper
    def _retry(func, attempts=5, base_backoff=0.5):
        last_exc = None
        for i in range(attempts):
            try:
                return func()
            except Exception as exc:
                last_exc = exc
                if i == attempts - 1:
                    raise
                time.sleep(base_backoff * (2 ** i))

    # support optional local embedding backend (e.g., Ollama)
    global _embedding_client
    if rag_enabled and emb_backend == "OLLAMA":
        class LocalOllamaClient:
            def __init__(self, host=None):
                self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

            def embed(self, texts, model="ollama-embedding"):
                try:
                    resp = requests.post(
                        f"{self.host}/api/embeddings",
                        json={"model": model, "input": texts},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return [item.get("embedding") for item in data.get("data", [])]
                except Exception:
                    return None

            def generate(self, prompt, model="ollama"):
                try:
                    resp = requests.post(
                        f"{self.host}/api/generate",
                        json={"model": model, "prompt": prompt},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # Ollama local API often returns {'response': 'text'} or streaming; handle common shapes
                    if isinstance(data, dict) and "response" in data:
                        return data.get("response")
                    # fallback: join text fields
                    return str(data)
                except Exception:
                    return ""

        _embedding_client = LocalOllamaClient()

    tools = []
    if rag_enabled:
        # Connect and build vector store only when an embedding-capable backend
        # is configured. Ollama chat-only installations should not trigger
        # LlamaIndex's implicit OpenAI embedding fallback.
        conn = _retry(lambda: psycopg2.connect(connection_string))
        conn.autocommit = True
        url = make_url(connection_string)
        _vector_store = _retry(lambda: PGVectorStore.from_params(
            database=db_name,
            host=url.host,
            password=url.password,
            port=url.port,
            user=url.username,
            table_name="LLMFutureOfAI",
            embed_dim=1536,
        ))
        _index = VectorStoreIndex.from_vector_store(vector_store=_vector_store)
        tools = [
            Tool(
                name="Article AI",
                func=lambda q: str(_index.as_query_engine().query(q)),
                description="Useful for article-specific knowledge queries.",
                return_direct=True,
            ),
        ]

    memory = ConversationBufferWindowMemory(memory_key="chat_history", k=6)

    # choose LLM backend: prefer local Ollama by default; only fall back to OpenAI if explicitly requested
    if llm_backend == "OLLAMA":
        host_env = os.getenv("OLLAMA_HOST")
        if host_env:
            llm = OllamaLLM(model=os.getenv("OLLAMA_MODEL", "llama3.1"), host=host_env)
        else:
            llm = OllamaLLM(model=os.getenv("OLLAMA_MODEL", "llama3.1"))
    elif OPENAI_API_KEY:
        llm = ChatOpenAI(temperature=0, api_key=OPENAI_API_KEY, model="gpt-4")
    else:
        class DummyLLM:
            def __init__(self):
                pass

            def __call__(self, *args, **kwargs):
                return ""

        llm = DummyLLM()
    _agent_executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent="conversational-react-description",
        memory=memory,
        verbose=True,
        handle_parsing_errors=False,
    )


# @traceable
def ask_openai_rag(message):
    try:
        _init_agent()
    except Exception as e:
        logging.exception("Agent initialization failed in ask_openai_rag")
        raise RuntimeError(f"agent_init_failed: {e}")

    try:
        return _agent_executor.run(input=f"{_career_context()}USER QUESTION:\n{message}")
    except Exception as e:
        logging.exception("Agent execution failed in ask_openai_rag")
        raise RuntimeError(f"agent_run_failed: {e}")


# @traceable
def chatbot(request):
    if request.method == "POST":
        message = request.POST.get("message")
        # Ensure agent is initialized; return 503 if initialization fails
        try:
            _init_agent()
        except Exception as e:
            logging.exception("Agent initialization failed")
            return JsonResponse({"error": "agent_init_failed", "details": str(e)}, status=503)

        try:
            response = _agent_executor.run(input=f"{_career_context()}USER QUESTION:\n{message}")
        except Exception as e:
            logging.exception("Agent execution failed")
            return JsonResponse({"error": "agent_run_failed", "details": str(e)}, status=500)

        return JsonResponse({"message": message, "response": response})
    return render(request, "chatbot.html")


@require_POST
def upload_profile(request):
    uploaded_file = request.FILES.get("profile")
    if uploaded_file is None:
        return JsonResponse({"error": "Choose a resume or profile file."}, status=400)

    try:
        content = _extract_profile_text(uploaded_file)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logging.exception("Profile extraction failed")
        return JsonResponse({"error": "The file could not be read."}, status=400)

    if not content:
        return JsonResponse({"error": "No readable text was found in that file."}, status=400)

    profile = CareerProfile.objects.first()
    if profile is None:
        profile = CareerProfile()
    profile.source_name = uploaded_file.name
    profile.content = content
    profile.save()
    return JsonResponse({"message": f"Loaded {uploaded_file.name}.", "characters": len(content)})
