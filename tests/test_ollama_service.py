"""HTTP requests are mocked so tests need no Ollama server."""

from unittest.mock import Mock

import pytest
import requests

from services.ollama_service import OllamaClient, OllamaError


def _client() -> OllamaClient:
    return OllamaClient("http://localhost:11434", 10, 600, ("localhost",))


def test_generate_passes_separate_connect_and_read_timeouts() -> None:
    client = _client()
    client.session.post = Mock(return_value=Mock(json=lambda: {"response": '{"reviews":[]}'}))
    assert client.generate("model", "prompt") == '{"reviews":[]}'
    assert client.session.post.call_args.kwargs["timeout"] == (10, 600)


@pytest.mark.parametrize("error,expected", [
    (requests.ConnectTimeout(), "接続がタイムアウト"),
    (requests.ReadTimeout(), "応答待ちがタイムアウト"),
])
def test_timeout_errors_distinguish_connection_from_response(error, expected: str) -> None:
    client = _client()
    client.session.post = Mock(side_effect=error)
    with pytest.raises(OllamaError, match=expected):
        client.generate("model", "prompt")


def test_model_listing_uses_short_read_timeout() -> None:
    client = _client()
    client.session.get = Mock(return_value=Mock(json=lambda: {"models": [{"name": "model"}]}))
    assert client.list_models() == ["model"]
    assert client.session.get.call_args.kwargs["timeout"] == (10, 15)
