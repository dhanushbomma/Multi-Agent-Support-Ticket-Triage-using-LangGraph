import pytest
from pydantic import ValidationError

from tests.fakes import FakeStructuredLLM
from triage.db import TicketStore
from triage.graph import build_graph, route_ticket, triage_ticket
from triage.schemas import Classification, Ticket

DRAFT = {"subject": "Re: your ticket", "body": "Thanks for reaching out, we're looking into it."}


def make(classification, priority, tmp_path):
    llm = FakeStructuredLLM(Classification=classification, PriorityAssessment=priority, DraftResponse=DRAFT)
    store = TicketStore(tmp_path / "t.db")
    return llm, store, build_graph(llm, store)


def ticket(tid="T1", msg="I was charged twice this month"):
    return Ticket(ticket_id=tid, customer="alice", message=msg)


def test_low_priority_gets_auto_reply(tmp_path):
    llm, store, g = make(
        {"category": "billing", "confidence": 0.9, "reasoning": "charge issue"},
        {"priority": "low", "reasoning": "question", "customer_sentiment": "neutral"},
        tmp_path,
    )
    out = triage_ticket(g, ticket())
    assert out["status"] == "auto_replied"
    assert out["draft"]["subject"] == "Re: your ticket"
    assert llm.calls == ["Classification", "PriorityAssessment", "DraftResponse"]


def test_urgent_ticket_escalates_without_drafting(tmp_path):
    llm, store, g = make(
        {"category": "technical", "confidence": 0.95, "reasoning": "outage"},
        {"priority": "urgent", "reasoning": "prod down", "customer_sentiment": "angry"},
        tmp_path,
    )
    out = triage_ticket(g, ticket("T2", "Production is down!"))
    assert out["status"] == "escalated"
    assert "urgent" in out["escalation_reason"]
    assert "DraftResponse" not in llm.calls


def test_low_confidence_escalates(tmp_path):
    _, _, g = make(
        {"category": "other", "confidence": 0.3, "reasoning": "unclear"},
        {"priority": "low", "reasoning": "x", "customer_sentiment": "neutral"},
        tmp_path,
    )
    out = triage_ticket(g, ticket("T3", "hmm?? stuff"))
    assert out["status"] == "escalated"
    assert "confidence" in out["escalation_reason"].lower()


def test_state_persisted_in_sqlite(tmp_path):
    _, store, g = make(
        {"category": "billing", "confidence": 0.9, "reasoning": "r"},
        {"priority": "medium", "reasoning": "r", "customer_sentiment": "neutral"},
        tmp_path,
    )
    triage_ticket(g, ticket("T4"))
    saved = store.get_state("T4")
    assert saved["status"] == "auto_replied"
    assert saved["classification"]["category"] == "billing"
    assert store.get_events("T4") == ["classify", "prioritize", "draft_response", "finalize"]
    assert store.list_by_status("auto_replied") == ["T4"]


def test_persistence_survives_reopen(tmp_path):
    _, store, g = make(
        {"category": "account", "confidence": 0.8, "reasoning": "r"},
        {"priority": "high", "reasoning": "r", "customer_sentiment": "angry"},
        tmp_path,
    )
    triage_ticket(g, ticket("T5"))
    reopened = TicketStore(tmp_path / "t.db")
    assert reopened.get_state("T5")["status"] == "escalated"
    assert reopened.get_state("missing") is None


def test_pydantic_rejects_invalid_llm_output():
    with pytest.raises(ValidationError):
        Classification(category="not_a_category", confidence=0.5, reasoning="x")
    with pytest.raises(ValidationError):
        Classification(category="billing", confidence=1.7, reasoning="x")
    with pytest.raises(ValidationError):
        Ticket(ticket_id="1", customer="a", message="")


@pytest.mark.parametrize(
    "prio,conf,expected",
    [("urgent", 0.9, "escalate"), ("high", 0.9, "escalate"),
     ("medium", 0.9, "draft_response"), ("low", 0.59, "escalate"), ("low", 0.6, "draft_response")],
)
def test_route_ticket(prio, conf, expected):
    state = {"priority": {"priority": prio}, "classification": {"confidence": conf}}
    assert route_ticket(state) == expected
