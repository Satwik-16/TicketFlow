"""
=============================================================================
Apexon AI Agent — Chat API Route Service
=============================================================================
Exposes the LangGraph agent to the frontend via a Server-Sent Events (SSE)
streaming endpoint.

Endpoint:
    POST /api/chat/stream
    Body: { "thread_id": "...", "message": "..." }
    Response: text/event-stream (SSE)

SSE Event Types:
    • event: status    → { "status": "Categorizing issue..." }
    • event: token     → { "content": "Here is..." }
    • event: ticket    → { "ticket_data": { ... } }
    • event: error     → { "error": "Something went wrong" }
    • event: done      → { "status": "complete" }

Architecture:
    ┌─────────────────┐     SSE Stream     ┌──────────────┐
    │  Frontend (Next) │◄──────────────────│  FastAPI SSE  │
    └─────────────────┘                    └──────┬───────┘
                                                  │
                                           ┌──────▼───────┐
                                           │  LangGraph   │
                                           │  astream_events│
                                           └──────────────┘

Usage:
    This router is mounted in mainAppService.py:
        app.include_router(chat_router, prefix="/api")
=============================================================================
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.core.agentGraphService import build_agent_graph

logger = logging.getLogger(__name__)

chat_router = APIRouter(tags=["Chat"])


class ChatStreamRequest(BaseModel):
    """
    Incoming chat request payload.

    Attributes:
        thread_id: Unique conversation thread identifier. If not provided,
                   a new UUID is generated for the session.
        message:   The user's message text to process.
    """

    thread_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique conversation thread ID. Auto-generated if omitted.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's message to the IT helpdesk agent.",
    )

def _sse_event(event_type: str, data: dict) -> dict:
    """
    Formats an SSE event dict for EventSourceResponse.

    Args:
        event_type: The SSE event name (status, token, ticket, error, done).
        data: The JSON-serializable payload.

    Returns:
        Dict with 'event' and 'data' keys for SSE streaming.
    """
    return {"event": event_type, "data": json.dumps(data)}


async def _stream_agent_response(
    request: Request,
    thread_id: str,
    message: str,
) -> AsyncGenerator[dict, None]:
    """
    Streams LangGraph agent events as SSE to the client.

    This generator:
      1. Sends a "status" event indicating processing has started.
      2. Invokes the LangGraph graph via astream_events (v2).
      3. Yields "token" events for LLM output chunks.
      4. Yields "status" events for node transitions.
      5. Yields "ticket" events when ticket_data is extracted.
      6. Sends a "done" event when processing is complete.

    Args:
        request: The FastAPI request object (for accessing app.state).
        thread_id: Conversation thread identifier.
        message: The user's message text.

    Yields:
        SSE event dicts consumed by EventSourceResponse.
    """
    # -------------------------------------------------------------------------
    # 1. Build the graph with the checkpoint saver from app.state
    # -------------------------------------------------------------------------
    checkpoint_saver = getattr(request.app.state, "checkpoint_saver", None)
    graph = build_agent_graph(checkpoint_saver=checkpoint_saver)

    config = {"configurable": {"thread_id": thread_id}}
    input_state = {"messages": [HumanMessage(content=message)]}

    # -------------------------------------------------------------------------
    # 2. Send initial status event
    # -------------------------------------------------------------------------
    yield _sse_event("status", {"status": "Processing your request..."})

    # -------------------------------------------------------------------------
    # 3. Stream events from the LangGraph agent
    # -------------------------------------------------------------------------
    try:

        async for event in graph.astream_events(
            input_state, config=config, version="v2"
        ):
            event_kind = event.get("event", "")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # -----------------------------------------------------------------
            # Node Start → Send status update
            # -----------------------------------------------------------------
            if event_kind == "on_chain_start" and event_name in {
                "categorize_issue",
                "execute_ticket",
                "search_and_respond",
                "handle_escalation",
            }:
                status_map = {
                    "categorize_issue": "🔍 Analyzing and categorizing your issue...",
                    "execute_ticket": "📝 Creating your support ticket...",
                    "search_and_respond": "🔎 Searching the knowledge base...",
                    "handle_escalation": "🚨 Preparing escalation for human review...",
                }
                yield _sse_event("status", {
                    "status": status_map.get(
                        event_name,
                        f"Processing: {event_name}...",
                    ),
                    "node": event_name,
                })

            # -----------------------------------------------------------------
            # LLM Token Streaming → Send token chunks
            # -----------------------------------------------------------------
            elif event_kind == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse_event("token", {"content": chunk.content})

            # -----------------------------------------------------------------
            # Node End → Check for ticket_data in output
            # -----------------------------------------------------------------
            elif event_kind == "on_chain_end":
                output = event_data.get("output", {})
                if not isinstance(output, dict):
                    continue

                if event_name == "categorize_issue":
                    ticket_data = output.get("ticket_data")
                    if ticket_data:
                        yield _sse_event("ticket", {
                            "ticket_data": ticket_data.model_dump()
                            if hasattr(ticket_data, "model_dump")
                            else ticket_data,
                        })

                # Nodes that return hardcoded messages (no streaming) need their
                # messages yielded as a single token chunk so the UI displays them.
                if event_name in {"categorize_issue", "handle_escalation"}:
                    print(f"\n--- ON_CHAIN_END: {event_name} ---")
                    print(f"OUTPUT TYPE: {type(output)}")
                    print(f"OUTPUT DATA: {repr(output)}")
                    msgs = output.get("messages", [])
                    print(f"MSGS: {repr(msgs)}")
                    if msgs:
                        last_msg = msgs[-1]
                        content = getattr(last_msg, "content", None)
                        if content is None and isinstance(last_msg, dict):
                            content = last_msg.get("content") or last_msg.get("kwargs", {}).get("content")
                        if content:
                            yield _sse_event("token", {"content": str(content)})

        # ---------------------------------------------------------------------
        # 4. Send completion event
        # ---------------------------------------------------------------------
        yield _sse_event("done", {
            "status": "complete",
            "thread_id": thread_id,
        })

    except Exception as exc:
        logger.exception("Error streaming agent response: %s", exc)
        yield _sse_event("error", {
            "error": str(exc),
            "thread_id": thread_id,
        })


@chat_router.post("/chat/stream")
async def chat_stream(body: ChatStreamRequest, request: Request) -> EventSourceResponse:
    """
    Receives a user message, invokes the LangGraph agent, and streams
    the response as Server-Sent Events.

    The client connects to this endpoint and receives real-time updates:
      • Status messages ("Categorizing issue...", "Creating ticket...")
      • Token-by-token LLM output for smooth typing animation
      • Structured ticket data when a ticket is created
      • A completion signal when processing is done

    Args:
        body: ChatStreamRequest with thread_id and message.
        request: FastAPI request object for accessing app.state.

    Returns:
        EventSourceResponse streaming SSE events.
    """
    logger.info(
        "Chat stream request: thread_id=%s message_length=%d",
        body.thread_id,
        len(body.message),
    )

    return EventSourceResponse(
        _stream_agent_response(
            request=request,
            thread_id=body.thread_id,
            message=body.message,
        ),
        media_type="text/event-stream",
    )


@chat_router.get("/chat/history")
async def get_chat_history(request: Request) -> dict:
    """
    Returns a list of the 50 most recently active thread IDs.
    Queries the PostgreSQL checkpoints table directly.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"threads": []}
        
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT thread_id, MAX(checkpoint_id) as latest_id
                    FROM checkpoints
                    GROUP BY thread_id
                    ORDER BY latest_id DESC
                    LIMIT 50
                """)
                records = await cur.fetchall()
                return {"threads": [r[0] for r in records]}
    except Exception as exc:
        logger.error("Error fetching chat history: %s", exc)
        return {"threads": []}


@chat_router.get("/chat/{thread_id}")
async def get_thread_state(thread_id: str, request: Request) -> dict:
    """
    Returns the parsed message history and ticket data for a specific thread,
    loaded directly from the LangGraph checkpoint saver.
    """
    checkpoint_saver = getattr(request.app.state, "checkpoint_saver", None)
    if not checkpoint_saver:
        return {"messages": []}
        
    graph = build_agent_graph(checkpoint_saver=checkpoint_saver)
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state_snapshot = await graph.aget_state(config)
        if not state_snapshot or not state_snapshot.values:
            return {"messages": []}
            
        raw_msgs = state_snapshot.values.get("messages", [])
        formatted = []
        
        for m in raw_msgs:
            formatted.append({
                "id": getattr(m, "id", str(uuid.uuid4())),
                "role": "user" if m.type == "human" else "assistant",
                "content": str(m.content)
            })
            
        ticket = state_snapshot.values.get("ticket_data")
        if ticket:
            formatted.append({
                "id": f"ticket-{thread_id}",
                "role": "ticket",
                "content": "",
                "ticketData": ticket.model_dump() if hasattr(ticket, "model_dump") else ticket
            })
            
        return {"messages": formatted}
    except Exception as exc:
        logger.error("Error fetching thread state for %s: %s", thread_id, exc)
        return {"messages": []}

