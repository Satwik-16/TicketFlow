"""
=============================================================================
Apexon AI Agent — Agent Nodes Service
=============================================================================
Implements the individual nodes of the LangGraph state machine. Each
node is a pure async function that receives the current ITAssistState
and returns a partial state update.

Node Architecture:
    categorize_issue  → LLM + structured output → ticket_data
    execute_ticket    → Calls ITSM tools based on ticket_data.intent
    search_and_respond→ Calls knowledge base for general Q&A
    handle_escalation → HITL interrupt for human review

Usage:
    These node functions are registered in agentGraphService.py:
        graph.add_node("categorize_issue", categorize_issue)
        graph.add_node("execute_ticket", execute_ticket)
=============================================================================
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.types import interrupt

from backend.core.agentStateService import ITAssistState
from backend.core.configCoreService import get_settings
from backend.core.mockItsmToolService import (
    create_itsm_ticket,
    search_knowledge_base,
)
from backend.core.ticketSchemaService import ITTicketExtraction

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds (exponential backoff: 2s, 4s, 8s)

_CATEGORIZATION_SYSTEM_PROMPT = """\
You are an expert IT helpdesk triage agent for a large enterprise.

Your job is to analyze the user's message and extract structured \
ticket data.

RULES:
1. Classify the intent as one of:
   - "access_request": User needs permissions, account access, \
or credentials.
   - "hardware_issue": Physical equipment problems (laptop, \
monitor, keyboard, etc.).
   - "general_qa": General IT questions that can be answered \
from a knowledge base.
   - "escalate": The issue is complex, ambiguous, or requires \
human judgment.
   - "irrelevant": Questions completely unrelated to IT, computers, or the enterprise.

2. Assess urgency:
   - "low": Non-urgent, informational, or routine requests (e.g., "How do I connect to WiFi").
   - "medium": Affects productivity but has a workaround or is non-blocking (e.g., "Need access to Jira", "Speaker doesn't work").
   - "high": Blocks the user's work completely, no workaround available (e.g., "Laptop won't turn on", "Account locked").
   - "critical": ONLY for escalation-worthy incidents (e.g., "Production database is unresponsive", "Security breach").

3. CRITICAL GUARDRAIL: You MUST NOT assign "critical" urgency \
unless the intent is "escalate". Violating this rule will cause \
a validation error.

4. Write a concise, clear summary (5-500 characters).

5. Assign the appropriate department based on the issue type.

IMPORTANT: Always evaluate urgency strictly based on the examples provided above to ensure absolute consistency. Do not overreact to capitalization or exclamation marks."""


def _build_categorization_llm() -> ChatGroq:
    """
    Constructs Groq LLM with structured output.

    Temperature = 0 for deterministic, consistent categorization.
    """
    settings = get_settings()
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.GROQ_API_KEY,
        temperature=0,
        max_retries=_MAX_RETRIES,
    )


def _build_response_llm() -> ChatGroq:
    """
    Constructs Groq LLM for generating
    human-readable responses (non-structured, conversational).
    """
    settings = get_settings()
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.GROQ_API_KEY,
        temperature=0.3,
        max_retries=_MAX_RETRIES,
    )


def _is_quota_error(error: Exception) -> bool:
    """Check if the error is a Groq API quota error."""
    error_str = str(error).lower()
    return (
        "429" in error_str
        or "quota" in error_str
        or "resource_exhausted" in error_str
    )


def _extract_user_messages(state: ITAssistState) -> list:
    """Extract human messages from the conversation state."""
    return [
        m for m in state["messages"]
        if hasattr(m, "type") and m.type == "human"
    ]


async def categorize_issue(state: ITAssistState) -> dict:
    """
    Analyzes the user's message and extracts structured ticket data
    using Groq with .with_structured_output().

    Includes retry logic with exponential backoff for transient
    API failures. Falls back to a safe default categorization if
    all retries fail.
    """
    logger.info("Node: categorize_issue — analyzing user message...")

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            llm = _build_categorization_llm()
            structured_llm = llm.with_structured_output(
                ITTicketExtraction
            )

            categorization_messages = [
                SystemMessage(
                    content=_CATEGORIZATION_SYSTEM_PROMPT
                ),
                *state["messages"],
            ]

            ticket_data: ITTicketExtraction = (
                await structured_llm.ainvoke(
                    categorization_messages
                )
            )

            logger.info(
                "Categorization result: intent=%s "
                "urgency=%s summary='%s'",
                ticket_data.intent,
                ticket_data.urgency,
                ticket_data.summary[:80],
            )

            intent = ticket_data.intent
            urgency = ticket_data.urgency

            result_dict = {
                "ticket_data": ticket_data,
                "requires_approval": intent == "escalate",
                "status_message": (
                    f"Categorized as: {intent} ({urgency})"
                ),
            }
            
            if intent == "escalate":
                result_dict["messages"] = [
                    AIMessage(
                        content=(
                            "🚨 **Escalation Required**\n\n"
                            "Your issue has been flagged as critical "
                            "and routed to the escalation queue. "
                            "It is currently paused pending human review "
                            "by the on-call engineer."
                        )
                    )
                ]
                
            return result_dict

        except Exception as exc:
            last_error = exc
            logger.warning(
                "categorize_issue attempt %d/%d failed: %s",
                attempt + 1,
                _MAX_RETRIES,
                str(exc)[:200],
            )

            if _is_quota_error(exc):
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.info(
                        "Quota error — retrying in %.1fs...",
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                break

            # Non-quota error — don't retry
            break

    # -----------------------------------------------------------------
    # Fallback: Safe default when API is unavailable
    # -----------------------------------------------------------------
    user_messages = _extract_user_messages(state)
    user_text = (
        user_messages[-1].content if user_messages
        else "IT help request"
    )

    error_detail = (
        str(last_error)[:200] if last_error else "Unknown error"
    )
    is_quota = (
        _is_quota_error(last_error) if last_error else False
    )

    logger.error(
        "categorize_issue failed after %d attempts: %s",
        _MAX_RETRIES,
        error_detail,
    )

    fallback_ticket = ITTicketExtraction(
        intent="escalate",
        urgency="medium",
        summary=f"Auto-escalated: {user_text[:200]}",
        department="IT Support",
    )

    if is_quota:
        error_msg = (
            "⚠️ **Groq API quota exceeded.** "
            "Your API key has reached "
            "its rate limit.\n\n"
            "**Your issue has been auto-escalated** "
            "to ensure nothing is lost.\n\n"
            "**To resolve:**\n"
            "1. Wait for the quota to reset\n"
            "2. Or update `GROQ_API_KEY` in `.env` "
            "with a paid API key\n"
            "3. Then restart the backend server\n\n"
            f"**Your message:** {user_text[:300]}"
        )
    else:
        error_msg = (
            f"⚠️ **Error during categorization:** "
            f"{error_detail}\n\n"
            "Your issue has been auto-escalated "
            "for manual review."
        )

    return {
        "ticket_data": fallback_ticket,
        "requires_approval": True,
        "status_message": "API error — auto-escalated",
        "messages": [AIMessage(content=error_msg)],
    }


async def execute_ticket(state: ITAssistState) -> dict:
    """
    Creates an ITSM ticket based on categorized ticket_data.
    Generates a human-readable confirmation message.
    """
    logger.info("Node: execute_ticket — creating ITSM ticket...")
    ticket_data = state["ticket_data"]

    if ticket_data is None:
        error_msg = "Cannot execute ticket: ticket_data is None."
        logger.error(error_msg)
        return {
            "messages": [AIMessage(content=f"⚠️ {error_msg}")],
            "status_message": "Error: Missing ticket data",
        }

    # Call the ITSM tool to create the ticket
    ticket_result = await create_itsm_ticket.ainvoke({
        "summary": ticket_data.summary,
        "intent": ticket_data.intent,
        "urgency": ticket_data.urgency,
        "department": ticket_data.department,
    })

    # Generate a conversational response
    try:
        llm = _build_response_llm()
        response_prompt = (
            "You are an IT helpdesk assistant. "
            "A ticket has been created with "
            f"these details:\n\n"
            f"{ticket_result}\n\n"
            "Generate a friendly, professional "
            "confirmation message for the user. "
            "Include the ticket details and let "
            "them know what to expect next."
        )

        response = await llm.ainvoke(
            [SystemMessage(content=response_prompt)]
        )

        return {
            "messages": [response],
            "status_message": "Ticket created successfully",
        }

    except Exception as exc:
        logger.warning(
            "Response LLM failed, returning raw ticket: %s",
            exc,
        )
        return {
            "messages": [AIMessage(
                content=(
                    "**Ticket Created Successfully**\n\n"
                    f"{ticket_result}\n\n"
                    "Our team will review your request "
                    "shortly."
                )
            )],
            "status_message": (
                "Ticket created (LLM response unavailable)"
            ),
        }


async def reject_query(state: ITAssistState) -> dict:
    """
    GARBAGE COLLECTION NODE: 
    Violently intercepts and halts queries marked as 'irrelevant'.
    We instantly overwrite ticket_data to None so the downstream system
    doesn't log a garbage ticket into the database queue.
    """
    logger.info("Node: reject_query — discarding irrelevant ticket.")

    return {
        "ticket_data": None,
        "messages": [AIMessage(content="This question is clearly irrelevant to IT Support. Please check Google.")],
        "status_message": "Query rejected autonomously."
    }


async def search_and_respond(state: ITAssistState) -> dict:
    """
    Searches the internal knowledge base for the user's question
    and generates a helpful response. Used when intent is
    'general_qa'.
    """
    logger.info(
        "Node: search_and_respond — searching knowledge base..."
    )

    user_messages = _extract_user_messages(state)
    query = (
        user_messages[-1].content if user_messages
        else "general IT help"
    )

    # Search the knowledge base
    kb_result = await search_knowledge_base.ainvoke(
        {"query": query}
    )

    # Generate a conversational response
    try:
        llm = _build_response_llm()
        response_prompt = (
            "You are an IT helpdesk assistant. "
            "Based on this knowledge base "
            f"article:\n\n"
            f"{kb_result}\n\n"
            "Answer the user's question naturally "
            "and helpfully. "
            "CRITICAL DIRECTIVE: If the user's question is NOT strictly related to IT, computers, software, or internal enterprise operations, DO NOT ATTEMPT TO ANSWER IT. Inform the user clearly that this question is irrelevant to IT Support, and assertively suggest they check Google instead. Do not apologize profusely."
        )

        response = await llm.ainvoke([
            SystemMessage(content=response_prompt),
            *state["messages"],
        ])

        return {
            "messages": [response],
            "status_message": "Found answer in knowledge base",
        }

    except Exception as exc:
        logger.warning(
            "Response LLM failed, returning raw KB: %s", exc,
        )
        return {
            "messages": [AIMessage(
                content=(
                    "📖 **Knowledge Base Result:**\n\n"
                    f"{kb_result}\n\n"
                    "_(AI summary unavailable — "
                    "showing raw KB article)_"
                )
            )],
            "status_message": (
                "KB result returned (LLM unavailable)"
            ),
        }


async def handle_escalation(state: ITAssistState) -> dict:
    """
    Triggers a Human-In-The-Loop interrupt for escalation-worthy
    issues. The graph execution pauses here until a human approves
    or rejects the escalation.
    """
    logger.info(
        "Node: handle_escalation — requesting human approval..."
    )
    ticket_data = state["ticket_data"]

    summary = ticket_data.summary if ticket_data else "N/A"
    urgency = ticket_data.urgency if ticket_data else "N/A"
    department = ticket_data.department if ticket_data else "N/A"

    escalation_summary = (
        "🚨 **Escalation Request**\n\n"
        f"- **Summary**: {summary}\n"
        f"- **Urgency**: {urgency}\n"
        f"- **Department**: {department}\n\n"
        "This issue requires human review "
        "before proceeding."
    )

    # INTERRUPT: Pause execution and wait for human input
    human_decision = interrupt(
        {
            "type": "escalation_review",
            "summary": escalation_summary,
            "ticket_data": (
                ticket_data.model_dump() if ticket_data else {}
            ),
            "prompt": (
                "Please approve or reject this escalation."
            ),
        }
    )

    if human_decision and human_decision.get("approved", False):
        logger.info("Escalation APPROVED by human reviewer.")
        return {
            "messages": [AIMessage(
                content=(
                    "✅ Escalation has been **approved** "
                    "by a human reviewer.\n\n"
                    f"{escalation_summary}\n\n"
                    "An on-call engineer has been notified "
                    "and will take over."
                )
            )],
            "status_message": (
                "Escalation approved — engineer notified"
            ),
        }

    logger.info("Escalation REJECTED by human reviewer.")
    return {
        "messages": [AIMessage(
            content=(
                "ℹ️ Escalation was **not approved** by the "
                "reviewer. Your issue will be handled through "
                "the standard support queue. A support ticket "
                "has been created for tracking."
            )
        )],
        "status_message": (
            "Escalation not approved — routed to standard queue"
        ),
    }
