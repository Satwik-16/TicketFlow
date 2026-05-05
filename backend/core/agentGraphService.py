"""
=============================================================================
Apexon AI Agent — Agent Graph Service
=============================================================================
Compiles the LangGraph StateGraph — the state machine that orchestrates
all agent behavior. This is the central nervous system of the application.

Graph Architecture:
    ┌────────┐
    │ START  │
    └───┬────┘
        │
        ▼
    ┌──────────────────┐
    │  categorize_issue │  ← Groq + structured output
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ intent_router()  │  ← Conditional edge based on ticket_data.intent
    └──┬──────┬────┬───┘
       │      │    │
       ▼      ▼    ▼
    ┌─────┐ ┌────┐ ┌─────────────┐
    │exec │ │ kb │ │ escalation  │
    │ticket│ │search│ │ (interrupt)  │
    └──┬──┘ └─┬──┘ └──────┬──────┘
       │      │           │
       ▼      ▼           ▼
    ┌────────────────────────┐
    │         END            │
    └────────────────────────┘

Usage:
    from backend.core.agentGraphService import build_agent_graph

    # With checkpoint saver (for persistence across requests):
    graph = build_agent_graph(checkpoint_saver=saver)

    # Invoke:
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="I need VPN access")]},
        config={"configurable": {"thread_id": "thread-123"}}
    )
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from backend.core.agentNodesService import (
    categorize_issue,
    execute_ticket,
    handle_escalation,
    search_and_respond,
    reject_query,
)
from backend.core.agentStateService import ITAssistState

logger = logging.getLogger(__name__)


def intent_router(state: ITAssistState) -> str:
    """
    Routes the graph based on the classified intent from categorize_issue.

    Routing Logic:
        - "general_qa"  → search_and_respond (knowledge base lookup)
        - "escalate"    → handle_escalation (HITL interrupt)
        - "access_request" | "hardware_issue" → execute_ticket (create ticket)

    Args:
        state: Current graph state with ticket_data populated.

    Returns:
        The name of the next node to execute.
    """
    ticket_data = state.get("ticket_data")

    if ticket_data is None:
        logger.warning("intent_router: ticket_data is None — routing to execute_ticket")
        return "execute_ticket"

    intent = ticket_data.intent

    routing_map: dict[str, str] = {
        "general_qa": "search_and_respond",
        "irrelevant": "reject_query",
        "escalate": "handle_escalation",
        "access_request": "execute_ticket",
        "hardware_issue": "execute_ticket",
    }

    destination = routing_map.get(intent, "execute_ticket")
    logger.info("intent_router: intent='%s' → routing to '%s'", intent, destination)
    return destination


def build_agent_graph(
    checkpoint_saver: BaseCheckpointSaver | None = None,
) -> Any:
    """
    Constructs and compiles the LangGraph StateGraph for the IT helpdesk agent.

    The graph implements a categorize-then-route pattern:
        1. User message enters → categorize_issue (LLM structured output)
        2. Conditional router inspects ticket_data.intent
        3. Routes to: execute_ticket | search_and_respond | handle_escalation
        4. Each terminal node → END

    Args:
        checkpoint_saver: Optional LangGraph checkpoint saver for persistence.
            When provided, enables conversation continuity across requests.

    Returns:
        A compiled LangGraph runnable (CompiledStateGraph).
    """
    logger.info("Building IT helpdesk agent graph...")

    # -------------------------------------------------------------------------
    # 1. Initialize the StateGraph with our state schema
    # -------------------------------------------------------------------------
    graph = StateGraph(ITAssistState)

    # -------------------------------------------------------------------------
    # 2. Register all nodes
    # -------------------------------------------------------------------------
    graph.add_node("categorize_issue", categorize_issue)
    graph.add_node("execute_ticket", execute_ticket)
    graph.add_node("search_and_respond", search_and_respond)
    graph.add_node("handle_escalation", handle_escalation)
    graph.add_node("reject_query", reject_query)

    # -------------------------------------------------------------------------
    # 3. Define edges
    # -------------------------------------------------------------------------

    # START → categorize_issue (always the first step)
    graph.add_edge(START, "categorize_issue")

    # categorize_issue → conditional router based on intent
    graph.add_conditional_edges(
        "categorize_issue",
        intent_router,
        {
            "execute_ticket": "execute_ticket",
            "search_and_respond": "search_and_respond",
            "handle_escalation": "handle_escalation",
            "reject_query": "reject_query",
        },
    )

    # All terminal nodes → END
    graph.add_edge("execute_ticket", END)
    graph.add_edge("search_and_respond", END)
    graph.add_edge("handle_escalation", END)
    graph.add_edge("reject_query", END)

    # -------------------------------------------------------------------------
    # 4. Compile with optional checkpoint saver
    # -------------------------------------------------------------------------
    compiled_graph = graph.compile(
        checkpointer=checkpoint_saver,
        interrupt_before=["handle_escalation"],
    )

    logger.info("IT helpdesk agent graph compiled successfully.")
    return compiled_graph
