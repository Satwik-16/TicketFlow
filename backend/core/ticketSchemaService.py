"""
=============================================================================
Apexon AI Agent — Ticket Schema Service
=============================================================================
Defines the structured output schema that the LLM must conform to when
categorizing IT helpdesk tickets. This is the primary guardrail layer.

Guardrails:
    • Intent is constrained to exactly 4 categories via Literal types.
    • Urgency is constrained to exactly 4 levels via Literal types.
    • A cross-field validator prevents the LLM from assigning "critical"
      urgency to any intent other than "escalate". This stops the model
      from over-escalating routine issues (e.g., a password reset request
      flagged as "critical"), which would spam the on-call team.

Usage:
    This model is passed to ChatGroq.with_structured_output()
    in the agent's categorizeIssue node (Phase 3).
=============================================================================
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


IntentType = Literal["access_request", "hardware_issue", "general_qa", "escalate", "irrelevant"]
UrgencyType = Literal["low", "medium", "high", "critical"]


class ITTicketExtraction(BaseModel):
    """
    Structured extraction schema for IT helpdesk ticket categorization.

    The LLM returns this exact shape via `.with_structured_output()`.
    Cross-field validation ensures the model cannot assign nonsensical
    combinations (e.g., a general Q&A marked as critical).

    Attributes:
        intent:   The classified category of the user's request.
        urgency:  The assessed urgency level.
        summary:  A concise, one-line summary of the issue.
        department: The department the ticket should be routed to.
    """

    intent: IntentType = Field(
        ...,
        description=(
            "Classified intent of the IT request. Must be one of: "
            "'access_request' (permission/account issues), "
            "'hardware_issue' (physical equipment problems), "
            "'general_qa' (general IT questions), "
            "'escalate' (requires human intervention), "
            "'irrelevant' (questions completely unrelated to IT or computers)."
        ),
    )

    urgency: UrgencyType = Field(
        ...,
        description=(
            "Assessed urgency level. 'critical' is reserved exclusively "
            "for escalation-worthy incidents."
        ),
    )

    summary: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Concise one-line summary of the reported issue.",
    )

    department: str = Field(
        default="IT General",
        max_length=100,
        description="Target department for ticket routing.",
    )

    # =========================================================================
    # Guardrail: Cross-Field Validation
    # =========================================================================
    @model_validator(mode="after")
    def validate_critical_urgency_requires_escalation(self) -> "ITTicketExtraction":
        """
        GUARDRAIL: Prevents the LLM from assigning 'critical' urgency
        to non-escalation intents.

        Rationale:
            'Critical' urgency triggers an on-call page. Allowing the LLM
            to mark routine requests (password resets, hardware inquiries)
            as 'critical' would flood the on-call rotation with noise,
            eroding trust in the system.

        Raises:
            ValueError: If urgency is 'critical' but intent is not 'escalate'.
        """
        if self.urgency == "critical" and self.intent != "escalate":
            raise ValueError(
                f"Urgency 'critical' is reserved exclusively for 'escalate' intent. "
                f"Received intent='{self.intent}' with urgency='critical'. "
                f"Please re-categorize using urgency='high' or lower."
            )
        return self
