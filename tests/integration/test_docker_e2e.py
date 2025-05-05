"""
Integration tests for the deployment toolkit API.

These tests require the service to be running in a Docker container.
"""
import pytest
import httpx


@pytest.mark.docker
def test_service_health():
    """Test the service health endpoint."""
    response = httpx.get("http://0.0.0.0:8080/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.docker
def test_service_with_fake_model():
    """Test the service invocation with minimal config.
    
    This test requires the service container to be running in deployment mode.
    """
    response = httpx.post(
        "http://0.0.0.0:8080/invoke", 
        json={"message": "Tell me a joke?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "content" in data
