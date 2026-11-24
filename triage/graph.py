"""LangGraph workflow.

    classify -> prioritize -> route -> draft_response -> finalize
                                   route -> escalate       -> finalize
"""
from langgraph.graph import END, START, StateGraph

from triage import prompts
from triage.db import TicketStore
from triage.schemas import (
    Category,
    Classification,
    DraftResponse,
    Priority,
    PriorityAssessment,
    Ticket,
    TriageState,
)

CONFIDENCE_THRESHOLD = 0.6


def get_llm():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def route_ticket(state: TriageState) -> str:
    """Pure routing function: decide whether a human must handle this ticket."""
    if state["priority"]["priority"] in (Priority.URGENT.value, Priority.HIGH.value):
        return "escalate"
    if state["classification"]["confidence"] < CONFIDENCE_THRESHOLD:
        return "escalate"
    return "draft_response"


def build_graph(llm, store: TicketStore):
    """Build and compile the workflow. `llm` must support `.with_structured_output()`."""

    classifier = llm.with_structured_output(Classification)
    prioritizer = llm.with_structured_output(PriorityAssessment)
    drafter = llm.with_structured_output(DraftResponse)

    def _log(state, node, payload):
        store.log_event(state["ticket"]["ticket_id"], node, payload)

    def classify(state: TriageState) -> dict:
        t = state["ticket"]
        result: Classification = classifier.invoke(
            prompts.CLASSIFY.format(customer=t["customer"], message=t["message"])
        )
        out = result.model_dump(mode="json")
        _log(state, "classify", out)
        return {"classification": out, "status": "classified"}

    def prioritize(state: TriageState) -> dict:
        t = state["ticket"]
        result: PriorityAssessment = prioritizer.invoke(
            prompts.PRIORITY.format(
                category=state["classification"]["category"],
                customer=t["customer"],
                message=t["message"],
            )
        )
        out = result.model_dump(mode="json")
        _log(state, "prioritize", out)
        return {"priority": out, "status": "prioritized", "route": route_ticket({**state, "priority": out})}

    def draft_response(state: TriageState) -> dict:
        t = state["ticket"]
        result: DraftResponse = drafter.invoke(
            prompts.DRAFT.format(
                category=state["classification"]["category"],
                priority=state["priority"]["priority"],
                customer=t["customer"],
                message=t["message"],
            )
        )
        out = result.model_dump(mode="json")
        _log(state, "draft_response", out)
        return {"draft": out, "status": "auto_replied"}

    def escalate(state: TriageState) -> dict:
        prio = state["priority"]["priority"]
        conf = state["classification"]["confidence"]
        reason = (
            f"Priority is {prio}" if prio in ("urgent", "high")
            else f"Low classification confidence ({conf:.2f})"
        )
        _log(state, "escalate", {"reason": reason})
        return {"escalation_reason": reason, "status": "escalated"}

    def finalize(state: TriageState) -> dict:
        store.save_state(dict(state))
        _log(state, "finalize", {"status": state["status"]})
        return {}

    g = StateGraph(TriageState)
    g.add_node("classify", classify)
    g.add_node("prioritize", prioritize)
    g.add_node("draft_response", draft_response)
    g.add_node("escalate", escalate)
    g.add_node("finalize", finalize)

    g.add_edge(START, "classify")
    g.add_edge("classify", "prioritize")
    g.add_conditional_edges(
        "prioritize", lambda s: s["route"], {"draft_response": "draft_response", "escalate": "escalate"}
    )
    g.add_edge("draft_response", "finalize")
    g.add_edge("escalate", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def triage_ticket(graph, ticket: Ticket) -> TriageState:
    return graph.invoke({"ticket": ticket.model_dump(), "status": "new"})
