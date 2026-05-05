"""
=============================================================================
Apexon AI Agent — Mock ITSM Tool Service
=============================================================================
Simulates interactions with enterprise IT Service Management platforms
(Jira, ServiceNow, etc.). These async functions act as LangChain tools
that the agent calls during the executeTicket node.

In production, these would be replaced with real API clients. The mock
implementations introduce a small delay to simulate network latency and
return realistic dummy responses.

Architecture:
    mockItsmToolService.py  ←── called by agentNodesService.executeTicket
         │
         ├── create_itsm_ticket()   → Creates a ticket in the mock ITSM
         └── search_knowledge_base()→ Searches internal KB for general Q&A

Usage:
    These functions are registered as LangChain tools via @tool decorator
    and bound to the agent in agentGraphService.py.
=============================================================================
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_SIMULATED_LATENCY_SECONDS = 0.3


def _generate_ticket_id() -> str:
    """Generates a realistic-looking ticket ID (e.g., 'INC-A1B2C3')."""
    return f"INC-{uuid.uuid4().hex[:6].upper()}"


@tool
async def create_itsm_ticket(
    summary: str,
    intent: str,
    urgency: str,
    department: str,
) -> str:
    """
    Creates a new IT support ticket in the ITSM system (Jira/ServiceNow).

    Args:
        summary: One-line description of the issue.
        intent: Ticket category (access_request, hardware_issue, etc.).
        urgency: Urgency level (low, medium, high, critical).
        department: Department to route the ticket to.

    Returns:
        A confirmation string with the ticket ID and details.
    """
    await asyncio.sleep(_SIMULATED_LATENCY_SECONDS)

    ticket_id = _generate_ticket_id()
    created_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "ITSM ticket created: id=%s intent=%s urgency=%s dept=%s",
        ticket_id,
        intent,
        urgency,
        department,
    )

    return (
        f"✅ Ticket **{ticket_id}** created successfully.\n"
        f"- **Summary**: {summary}\n"
        f"- **Category**: {intent}\n"
        f"- **Urgency**: {urgency}\n"
        f"- **Department**: {department}\n"
        f"- **Created At**: {created_at}\n"
        f"- **Status**: Open\n\n"
        f"A support engineer has been notified and will respond shortly."
    )


@tool
async def search_knowledge_base(query: str) -> str:
    """
    Searches the internal IT knowledge base for answers to general questions.

    Used for 'general_qa' intents where no ticket creation is needed.

    Args:
        query: The user's question or search query.

    Returns:
        A formatted knowledge base article summary.
    """
    await asyncio.sleep(_SIMULATED_LATENCY_SECONDS)

    logger.info("Knowledge base search: query='%s'", query)

    # -------------------------------------------------------------------------
    # Simulated KB responses mapped to common IT queries
    # -------------------------------------------------------------------------
    kb_responses = {
        "vpn": (
            "🔍 **KB Article: VPN Setup Guide**\n\n"
            "To connect to the corporate VPN:\n"
            "1. Download the VPN client from the IT portal.\n"
            "2. Use your SSO credentials to authenticate.\n"
            "3. Select the nearest gateway server.\n"
            "4. If issues persist, contact IT Support with error screenshots."
        ),
        "password": (
            "🔍 **KB Article: Password Reset Procedure**\n\n"
            "To reset your password:\n"
            "1. Navigate to https://sso.company.com/reset\n"
            "2. Enter your employee ID and registered email.\n"
            "3. Follow the verification steps sent to your email.\n"
            "4. New password must meet complexity requirements (12+ chars)."
        ),
        "software": (
            "🔍 **KB Article: Software Installation Requests**\n\n"
            "To request new software:\n"
            "1. Submit a request through the IT Self-Service Portal.\n"
            "2. Include the software name, version, and business justification.\n"
            "3. Approvals are processed within 2 business days.\n"
            "4. Licensed software requires manager approval."
        ),
    }

    # Match query against known topics, fallback to generic response
    query_lower = query.lower()
    for keyword, response in kb_responses.items():
        if keyword in query_lower:
            return response

    return (
        "🔍 **Knowledge Base Search Results**\n\n"
        f"No exact match found for: *\"{query}\"*\n\n"
        "**Suggested next steps:**\n"
        "1. Try rephrasing your question with specific keywords.\n"
        "2. Browse the IT Self-Service Portal for common solutions.\n"
        "3. If your issue is urgent, I can create a support ticket for you."
    )
