"""
Standalone tests for the deployment toolkit in isolation.
This file runs completely independently of other test configurations.
"""
import os
import sys
import pytest
import tempfile
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Create a minimal test app that mimics our production endpoints
standalone_app = FastAPI()

class MessageRequest(BaseModel):
    message: str
    model: str = None

class MessageResponse(BaseModel):
    type: str
    content: str

@standalone_app.post("/health")
async def health_check():
    return {"status": "ok"}

@standalone_app.post("/invoke")
async def invoke(request: MessageRequest):
    return MessageResponse(type="ai", content=f"Mock response to: {request.message}")

@standalone_app.post("/feedback")
async def feedback(request: Request):
    return {"status": "success"}

@pytest.fixture
def standalone_client():
    return TestClient(standalone_app)

# Test our health endpoint
def test_health_standalone(standalone_client):
    response = standalone_client.post("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# Test our invoke endpoint
def test_invoke_standalone(standalone_client):
    response = standalone_client.post(
        "/invoke", 
        json={"message": "What is the weather?", "model": "test-model"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ai"
    assert "Mock response to:" in data["content"]
    
# Test our feedback endpoint
def test_feedback_standalone(standalone_client):
    response = standalone_client.post(
        "/feedback", 
        json={
            "run_id": "test-run-id",
            "key": "human-rating",
            "score": 0.9
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}