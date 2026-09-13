from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
import os

from . import views
from .ollama import OllamaLLM


class InitAgentTests(TestCase):
	def setUp(self):
		os.environ["RAG_ENABLED"] = "1"

	def tearDown(self):
		# reset globals after each test
		views._agent_executor = None
		views._index = None
		views._vector_store = None
		views._embedding_client = None

	@patch("app.chatbot.views.PGVectorStore.from_params")
	@patch("app.chatbot.views.VectorStoreIndex.from_vector_store")
	@patch("app.chatbot.views.initialize_agent")
	def test_retry_connects_on_transient_db_errors(self, mock_init_agent, mock_index_from_vs, mock_pg_from_params):
		# simulate psycopg2.connect failing twice then succeeding
		calls = []

		def fake_connect(conn_str):
			if len(calls) < 2:
				calls.append(1)
				raise Exception("db not ready")
			return MagicMock()

		with patch("app.chatbot.views.psycopg2.connect", side_effect=fake_connect):
			mock_pg_from_params.return_value = MagicMock()
			mock_index_from_vs.return_value = MagicMock()
			mock_init_agent.return_value = MagicMock()
			os.environ["DB_CONNECTION_STRING"] = "postgresql://user:pass@db:5432/testdb"
			os.environ["DB_NAME"] = "testdb"
			# should not raise
			views._init_agent()
			self.assertTrue(len(calls) == 2)

	@patch("app.chatbot.views.PGVectorStore.from_params")
	@patch("app.chatbot.views.VectorStoreIndex.from_vector_store")
	@patch("app.chatbot.views.initialize_agent")
	def test_ollama_selected_without_openai_key(self, mock_init_agent, mock_index_from_vs, mock_pg_from_params):
		mock_pg_from_params.return_value = MagicMock()
		mock_index_from_vs.return_value = MagicMock()
		mock_init_agent.return_value = MagicMock()
		os.environ["DB_CONNECTION_STRING"] = "postgresql://user:pass@db:5432/testdb"
		os.environ["DB_NAME"] = "testdb"
		os.environ.pop("OPENAI_API_KEY", None)
		with patch("app.chatbot.views.psycopg2.connect", return_value=MagicMock()):
			os.environ["EMBEDDING_BACKEND"] = "OLLAMA"

			views._init_agent()
			self.assertIsNotNone(views._embedding_client)

	def test_ollama_llm_calls_local_api(self):
		# ensure OllamaLLM calls the local generate endpoint and returns text
		llm = OllamaLLM(model="test-model", host="http://local-ollama")
		# simulate streaming response lines
		class FakeStream:
			def __init__(self, lines):
				self._lines = lines

			def raise_for_status(self):
				return None

			def iter_lines(self, decode_unicode=True):
				for l in self._lines:
					yield l

		lines = [
			'{"token":"hello "}',
			'{"token":"world"}',
		]

		fake_stream = FakeStream(lines)

		cb = MagicMock()
		# inject callback manager
		llm.callback_manager = cb

		with patch("app.chatbot.ollama.requests.post", return_value=fake_stream) as mock_post:
			out = llm._call("say hi")
			self.assertEqual(out, "hello world")
			# ensure callback was called for tokens
			self.assertTrue(cb.on_llm_new_token.called)
			mock_post.assert_called()

	def test_profile_upload_stores_resume_text(self):
		resume = SimpleUploadedFile(
			"resume.txt",
			b"Python developer\nBuilt ETL pipelines with pandas and PostgreSQL.",
			content_type="text/plain",
		)
		response = self.client.post("/upload-profile/", {"profile": resume})

		self.assertEqual(response.status_code, 200)
		self.assertGreater(response.json()["characters"], 0)
		self.assertIn("pandas", views.CareerProfile.objects.get().content)

	def test_profile_upload_rejects_unsupported_file(self):
		profile = SimpleUploadedFile("resume.exe", b"not a resume")
		response = self.client.post("/upload-profile/", {"profile": profile})

		self.assertEqual(response.status_code, 400)
