"""
=============================================================================
Apexon AI Agent — Agent State Service
=============================================================================
Defines the LangGraph state schema (TypedDict) that flows through every
node in the agent's state machine.

Architecture:
    Every node receives this state as input and returns a partial update.
    LangGraph merges the update into the existing state automatically.

    ┌─────────────────────────────────────────────┐
    │               ITAssistState                  │
    │                                             │
    │  messages:        list[BaseMessage]          │ ← add_messages reducer
    │  ticket_data:     ITTicketExtraction | None  │ ← from categorizeIssue
    │  requires_approval: bool                     │ ← triggers HITL interrupt
    │  status_message:  str                        │ ← streamed to frontend
    └─────────────────────────────────────────────┘

Usage:
    from backend.core.agentStateService import ITAssistState
=============================================================================
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from backend.core.ticketSchemaService import ITTicketExtraction


class ITAssistState(TypedDict):
    """
    LangGraph state flowing through the IT Helpdesk Agent graph.

    Attributes:
        messages:
            Conversation history. Uses the `add_messages` reducer so that
            each node can append messages without replacing the full list.

        ticket_data:
            Structured extraction output from the categorizeIssue node.
            `None` until the LLM has categorized the user's request.

        requires_approval:
            Set to `True` when the intent is 'escalate'. This triggers
            a Human-In-The-Loop interrupt in the graph, halting execution
            until a human approves or rejects the escalation.

        status_message:
            Lightweight status string streamed to the frontend as an SSE
            metadata event (e.g., "Categorizing issue...", "Creating ticket...").
            Allows the UI to show progress before the final answer arrives.
    """

    # -------------------------------------------------------------------------
    # Conversation history — append-only via add_messages reducer
    # -------------------------------------------------------------------------
    messages: Annotated[list[BaseMessage], add_messages]

    # -------------------------------------------------------------------------
    # Structured ticket extraction (populated by categorizeIssue node)
    # -------------------------------------------------------------------------
    ticket_data: ITTicketExtraction | None

    # -------------------------------------------------------------------------
    # Human-In-The-Loop flag (set by conditional router for escalations)
    # -------------------------------------------------------------------------
    requires_approval: bool

    # -------------------------------------------------------------------------
    # Status message for frontend SSE streaming
    # -------------------------------------------------------------------------
    status_message: str
