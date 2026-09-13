import os
import requests
import json
from typing import List, Optional

from langchain.llms.base import LLM
from langchain.schema import LLMResult, Generation


class OllamaLLM(LLM):
    """A minimal LangChain-compatible LLM wrapper for local Ollama HTTP API.

    It implements `_call` and `_generate` expected by `langchain.llms.base.LLM`.
    """

    model: str = "ollama"
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    @property
    def _identifying_params(self):
        return {"model": self.model, "host": self.host}

    @property
    def _llm_type(self) -> str:
        return "ollama"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        # single prompt convenience wrapper
        result = self._generate([prompt], stop=stop)
        # extract first generation text
        try:
            out = result.generations[0][0].text
            if out:
                return out
        except Exception:
            pass
        # fallback to last_stream_text when streaming produced tokens
        return getattr(self, "_last_stream_text", "")

    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None) -> LLMResult:
        # Call Ollama local /api/generate for each prompt and return LLMResult
        generations = []
        for p in prompts:
            text = ""
            try:
                # try streaming first
                resp = requests.post(
                    f"{self.host}/api/generate",
                    json={"model": self.model, "prompt": p},
                    timeout=30,
                    stream=True,
                )
                resp.raise_for_status()
                # iterate over streamed lines and emit callbacks for tokens
                if hasattr(resp, "iter_lines"):
                    for raw in resp.iter_lines(decode_unicode=True):
                        if not raw:
                            continue
                        piece = raw
                        # try to parse JSON line
                        try:
                            obj = json.loads(piece)
                        except Exception:
                            obj = None

                        chunk = None
                        if isinstance(obj, dict) and "token" in obj:
                            chunk = obj.get("token") or ""
                        elif isinstance(obj, dict) and "response" in obj:
                            chunk = obj.get("response") or ""
                        else:
                            # fallback: try to extract token via simple parsing
                            try:
                                if isinstance(piece, str) and '"token"' in piece:
                                    start = piece.find('"token"')
                                    token_start = piece.find(':', start) + 1
                                    token_text = piece[token_start:].strip()
                                    token_text = token_text.strip().lstrip('{').rstrip('}').strip()
                                    token_text = token_text.strip('"')
                                    chunk = token_text
                                else:
                                    chunk = piece
                            except Exception:
                                chunk = piece

                        if chunk:
                            text += chunk
                            # expose last_stream_text for callers that rely on streaming accumulation
                            try:
                                self._last_stream_text = text
                            except Exception:
                                pass
                            # notify callbacks if present
                            if getattr(self, "callback_manager", None):
                                try:
                                    self.callback_manager.on_llm_new_token(chunk)
                                except Exception:
                                    pass
                    # finished streaming
                else:
                    data = resp.json()
                    if isinstance(data, dict) and "response" in data:
                        text = data.get("response")
                    else:
                        text = str(data)
            except Exception:
                text = ""
            generations.append([Generation(text=text)])

        return LLMResult(generations=generations, llm_output={})
