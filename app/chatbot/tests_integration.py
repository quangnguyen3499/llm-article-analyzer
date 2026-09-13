import os
import unittest
import requests

from django.test import SimpleTestCase


@unittest.skipUnless(os.getenv("RUN_OLLAMA_INTEGRATION") == "1", "Ollama integration tests skipped")
class OllamaIntegrationTests(SimpleTestCase):
    def test_generate_endpoint(self):
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        resp = requests.post(f"{host}/api/generate", json={"model": "ollama", "prompt": "hello"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        assert data, "Empty response from Ollama generate"

    def test_embeddings_endpoint(self):
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        resp = requests.post(f"{host}/api/embeddings", json={"model": "ollama-embedding", "input": ["a"]}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        assert data, "Empty response from Ollama embeddings"
