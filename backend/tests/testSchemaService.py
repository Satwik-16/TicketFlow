"""
=============================================================================
Apexon AI Agent — Schema Guardrail Tests
=============================================================================
Validates that the ITTicketExtraction Pydantic model correctly enforces
the cross-field guardrail: 'critical' urgency is reserved exclusively
for 'escalate' intent.

Run:
    pytest backend/tests/testSchemaService.py -v
=============================================================================
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.ticketSchemaService import ITTicketExtraction


# =============================================================================
# Fixtures
# =============================================================================
VALID_SUMMARY = "User cannot access the VPN after password rotation."


# =============================================================================
# Positive Tests — Valid Combinations
# =============================================================================
class TestValidTicketCombinations:
    """Ensures all valid intent+urgency combinations are accepted."""

    def test_escalate_with_critical_urgency(self) -> None:
        """The only valid path to 'critical' urgency."""
        ticket = ITTicketExtraction(
            intent="escalate",
            urgency="critical",
            summary=VALID_SUMMARY,
        )
        assert ticket.intent == "escalate"
        assert ticket.urgency == "critical"

    def test_escalate_with_non_critical_urgency(self) -> None:
        """Escalation can also have lower urgency — not all escalations are critical."""
        ticket = ITTicketExtraction(
            intent="escalate",
            urgency="high",
            summary=VALID_SUMMARY,
        )
        assert ticket.urgency == "high"

    @pytest.mark.parametrize(
        "intent,urgency",
        [
            ("access_request", "low"),
            ("access_request", "medium"),
            ("access_request", "high"),
            ("hardware_issue", "low"),
            ("hardware_issue", "medium"),
            ("hardware_issue", "high"),
            ("general_qa", "low"),
            ("general_qa", "medium"),
            ("general_qa", "high"),
        ],
    )
    def test_non_critical_urgency_with_any_intent(
        self, intent: str, urgency: str
    ) -> None:
        """Non-critical urgency is valid for any intent."""
        ticket = ITTicketExtraction(
            intent=intent,  # type: ignore[arg-type]
            urgency=urgency,  # type: ignore[arg-type]
            summary=VALID_SUMMARY,
        )
        assert ticket.intent == intent
        assert ticket.urgency == urgency

    def test_default_department(self) -> None:
        """Department defaults to 'IT General' when not specified."""
        ticket = ITTicketExtraction(
            intent="general_qa",
            urgency="low",
            summary=VALID_SUMMARY,
        )
        assert ticket.department == "IT General"

    def test_custom_department(self) -> None:
        """Department can be overridden by the LLM output."""
        ticket = ITTicketExtraction(
            intent="access_request",
            urgency="medium",
            summary=VALID_SUMMARY,
            department="Identity & Access Management",
        )
        assert ticket.department == "Identity & Access Management"


# =============================================================================
# Negative Tests — Guardrail Enforcement
# =============================================================================
class TestGuardrailEnforcement:
    """Ensures the cross-field validator rejects invalid combinations."""

    @pytest.mark.parametrize(
        "intent",
        ["access_request", "hardware_issue", "general_qa"],
    )
    def test_critical_urgency_rejected_for_non_escalation_intents(
        self, intent: str
    ) -> None:
        """
        GUARDRAIL: 'critical' urgency MUST be rejected for all intents
        except 'escalate'. This prevents the LLM from over-escalating
        routine requests.
        """
        with pytest.raises(ValidationError) as exc_info:
            ITTicketExtraction(
                intent=intent,  # type: ignore[arg-type]
                urgency="critical",
                summary=VALID_SUMMARY,
            )

        # Verify the error message mentions the intent that was rejected
        error_text = str(exc_info.value)
        assert "critical" in error_text.lower()
        assert "escalate" in error_text.lower()

    def test_invalid_intent_rejected(self) -> None:
        """Literal type constraint prevents arbitrary intent strings."""
        with pytest.raises(ValidationError):
            ITTicketExtraction(
                intent="random_category",  # type: ignore[arg-type]
                urgency="low",
                summary=VALID_SUMMARY,
            )

    def test_invalid_urgency_rejected(self) -> None:
        """Literal type constraint prevents arbitrary urgency strings."""
        with pytest.raises(ValidationError):
            ITTicketExtraction(
                intent="general_qa",
                urgency="urgent",  # type: ignore[arg-type]
                summary=VALID_SUMMARY,
            )

    def test_summary_too_short(self) -> None:
        """Summary must be at least 5 characters."""
        with pytest.raises(ValidationError):
            ITTicketExtraction(
                intent="general_qa",
                urgency="low",
                summary="Hi",
            )

    def test_empty_summary_rejected(self) -> None:
        """Summary cannot be empty."""
        with pytest.raises(ValidationError):
            ITTicketExtraction(
                intent="general_qa",
                urgency="low",
                summary="",
            )
