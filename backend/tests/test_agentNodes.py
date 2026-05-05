import pytest
from langchain_core.messages import HumanMessage

from backend.core.agentStateService import ITAssistState
from backend.core.agentNodesService import categorize_issue
from backend.core.ticketSchemaService import ITTicketExtraction

@pytest.mark.asyncio
async def test_categorize_issue_low():
    """
    Test that categorize_issue correctly intercepts an intent as low urgency 
    and does not require approval.
    """
    state: ITAssistState = {
        "messages": [HumanMessage(content="How do I setup my work email on my phone?")],
        "ticket_data": None,
        "requires_approval": False,
        "status_message": "",
        "next": ""
    }
    
    # We invoke categorize_issue
    # Since this triggers a real robust prompt with few-shot examples, 
    # it should reliably output low urgency.
    output = await categorize_issue(state)
    
    assert "ticket_data" in output
    assert output["ticket_data"].intent in ["general_qa", "access_request"]
    assert output["ticket_data"].urgency in ["low", "medium"]
    assert output["requires_approval"] is False

@pytest.mark.asyncio
async def test_categorize_issue_escalate():
    """
    Test that categorize_issue correctly spots a critical escalation 
    and sets requires_approval to True.
    """
    state: ITAssistState = {
        "messages": [HumanMessage(content="EMERGENCY!! Production database is totally unresponsive and down!!")],
        "ticket_data": None,
        "requires_approval": False,
        "status_message": "",
        "next": ""
    }
    
    output = await categorize_issue(state)
    
    assert "ticket_data" in output
    assert output["ticket_data"].intent == "escalate"
    assert output["ticket_data"].urgency == "critical"
    # Escalations explicitly require approval
    assert output["requires_approval"] is True
    assert "messages" in output
