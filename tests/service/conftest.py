from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

# Mock the agents module before importing app
with patch.dict('sys.modules', {
    'agents': Mock(),
    'agents.agents': Mock(),
    'agents.research_assistant': Mock()
}):
    from service import app


@pytest.fixture(autouse=True)
def mock_agents():
    """Mock the agents module to prevent actual LLM initialization."""
    with patch('agents.agents.DEFAULT_AGENT', 'default_agent'):
        with patch('agents.agents.get_agent') as mock_get_agent:
            agent_mock = AsyncMock()
            agent_mock.ainvoke = AsyncMock(
                return_value=[("values", {"messages": [AIMessage(content="Test response")]})]
            )
            agent_mock.get_state = Mock()
            mock_get_agent.return_value = agent_mock
            yield agent_mock


@pytest.fixture
def test_client():
    """Fixture to create a FastAPI test client."""
    # Patch settings to force deployment mode during tests
    with patch("core.settings.settings.MODE", "deployment"):
        return TestClient(app)


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent that can be configured for different test scenarios."""
    agent_mock = AsyncMock()
    agent_mock.ainvoke = AsyncMock(
        return_value=[("values", {"messages": [AIMessage(content="Test response")]})]
    )
    agent_mock.get_state = Mock()  # Default empty mock for get_state
    with patch("service.service.get_agent", Mock(return_value=agent_mock)):
        yield agent_mock


@pytest.fixture
def mock_settings():
    """Fixture to ensure settings are clean for each test."""
    with patch("service.service.settings") as mock_settings:
        # Configure settings for deployment mode
        mock_settings.MODE = "deployment"
        mock_settings.DEFAULT_MODEL = "placeholder-model"
        mock_settings.AVAILABLE_MODELS = {"placeholder-model"}
        yield mock_settings


@pytest.fixture
def mock_httpx():
    """Patch httpx.stream and httpx.get to use our test client."""

    with TestClient(app) as client:

        def mock_stream(method: str, url: str, **kwargs):
            # Strip the base URL since TestClient expects just the path
            path = url.replace("http://0.0.0.0", "")
            return client.stream(method, path, **kwargs)

        def mock_get(url: str, **kwargs):
            # Strip the base URL since TestClient expects just the path
            path = url.replace("http://0.0.0.0", "")
            return client.get(path, **kwargs)

        with patch("httpx.stream", mock_stream):
            with patch("httpx.get", mock_get):
                yield
