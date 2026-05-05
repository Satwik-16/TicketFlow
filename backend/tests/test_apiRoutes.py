import pytest
from httpx import AsyncClient, ASGITransport
from backend.mainAppService import app

@pytest.mark.asyncio
async def test_chat_history_endpoint():
    """
    Test the custom GET /api/chat/history endpoint directly.
    """
    # Use ASGITransport to test FastAPI endpoints directly in memory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/chat/history")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate schema
        assert "threads" in data
        assert isinstance(data["threads"], list)

@pytest.mark.asyncio
async def test_chat_stream_endpoint():
    """
    Ensure the SSE endpoint accepts POST requests and returns a valid SSE stream.
    We don't need to read the whole stream, just verify 200 OK and text/event-stream.
    """
    payload = {
        "thread_id": "test-thread-123",
        "message": "Ping test"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Stream the request since it's SSE
        async with ac.stream("POST", "/api/chat/stream", json=payload) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            
            # Read the first chunk to ensure the generator started
            chunk = await response.aiter_lines().__anext__()
            assert "event: status" in chunk or "event:" in chunk
