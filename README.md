# 🎫 Multi-Agent Support Ticket Triage

> A LangGraph workflow that reads a support ticket, works out what it is and how urgent it is, then either drafts a reply or hands it to a human.

![Python](https://img.shields.io/badge/python-3.11-blue) ![LangGraph](https://img.shields.io/badge/LangGraph-stateful-purple) ![Pydantic](https://img.shields.io/badge/Pydantic-validated-e92063) ![SQLite](https://img.shields.io/badge/SQLite-persisted-003B57)

## Why I built this

Support teams get a mix of tickets: "how do I change my email?" sits in the same queue as "production is down and we're losing money". Treating them the same wastes time on one and risks the other.

I wanted to see how far a small, well-structured agent workflow could go. The key idea is that **the AI should not answer everything**. Some tickets should be answered automatically and some should go straight to a person, and the system has to decide which, in a way that can be tested.

## What it does

For every ticket it:

1. **Classifies** it: `billing`, `technical`, `account`, `feature_request` or `other`, with a confidence score
2. **Assesses priority**: `low`, `medium`, `high` or `urgent`, plus the customer's sentiment
3. **Routes it**: auto-reply or escalate to a human
4. **Drafts a reply** (auto-reply path only)
5. **Saves everything** to SQLite, including an audit trail of each step

## The workflow

```
START ─► classify ─► prioritize ──┬──► draft_response ──► finalize ─► END
                                  │                          ▲
                                  └──► escalate ─────────────┘
```

### The routing rule

This is the heart of the project, and it is a plain function you can read in one glance (`route_ticket` in `triage/graph.py`):

| Situation | Route |
|---|---|
| Priority is `urgent` or `high` | **Escalate** |
| Classifier confidence is below 0.6 | **Escalate** |
| Anything else | **Auto-draft a reply** |

Routing is ordinary Python rather than another LLM call, so the decision is deterministic, explainable and unit-tested. The LLM does the language work (understanding and writing), and code makes the safety decision.

### Structured outputs

Each LLM step is bound to a Pydantic model with `with_structured_output(...)`:

| Step | Model | Key fields |
|---|---|---|
| classify | `Classification` | `category` (enum), `confidence` (0 to 1), `reasoning` |
| prioritize | `PriorityAssessment` | `priority` (enum), `customer_sentiment`, `reasoning` |
| draft | `DraftResponse` | `subject`, `body` (min length enforced) |

If the model returns something invalid, such as a made-up category or a confidence of 1.7, validation fails right there instead of the bad value flowing through the rest of the pipeline.

### Persistence

`triage/db.py` uses two SQLite tables:

- `tickets`: the final state of each ticket (upserted, so re-running a ticket updates it)
- `events`: an ordered log of every node that ran, e.g. `classify → prioritize → draft_response → finalize`

That gives you a basic audit trail: for any ticket you can see what happened and in what order.

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/ticket-triage.git
cd ticket-triage
cp .env.example .env            # add your OPENAI_API_KEY
pip install -r requirements.txt

python main.py "I was charged twice this month" --customer alice
```

It prints the full final state as JSON. For a routine ticket you'll see something like:

```json
{
  "ticket": {"ticket_id": "a1b2c3d4", "customer": "alice", "message": "I was charged twice this month"},
  "classification": {"category": "billing", "confidence": 0.9, "reasoning": "..."},
  "priority": {"priority": "medium", "customer_sentiment": "frustrated", "reasoning": "..."},
  "draft": {"subject": "...", "body": "..."},
  "route": "draft_response",
  "status": "auto_replied"
}
```

(Exact wording will vary by model.) An urgent ticket ends with `"status": "escalated"` and an `escalation_reason` instead of a draft.

### Using it from Python

```python
from triage.db import TicketStore
from triage.graph import build_graph, get_llm, triage_ticket
from triage.schemas import Ticket

store = TicketStore("tickets.db")
graph = build_graph(get_llm(), store)

result = triage_ticket(graph, Ticket(ticket_id="T-1", customer="bob", message="Our site is down!"))
print(result["status"])                  # escalated
print(store.list_by_status("escalated")) # ['T-1']
```

## Project layout

```
triage/
  schemas.py   Pydantic models, enums and the graph's state definition
  prompts.py   Prompt templates for the three LLM steps
  graph.py     The LangGraph workflow and routing function
  db.py        SQLite storage and audit log
main.py        Small CLI
tests/         Pytest suite with a scripted fake LLM
```

## Testing

```bash
pytest -q
```

Tests don't call a real model. `tests/fakes.py` provides a scripted LLM that returns exactly the structured outputs a test specifies, so each scenario is repeatable. The suite covers:

- A low-priority ticket gets an auto-reply (and all three LLM steps run)
- An urgent ticket escalates **without** drafting a reply
- Low classifier confidence escalates
- State and event history are saved to SQLite and survive reopening the database
- Pydantic rejects invalid categories, out-of-range confidence and empty messages
- The routing function at its boundaries (confidence 0.59 vs 0.6)

## Design choices worth mentioning

- **Dependency injection for the LLM.** `build_graph(llm, store)` takes the model as an argument, which is what makes the tests possible and makes it easy to swap providers
- **Code decides, LLM describes.** Anything with consequences (escalate or not) lives in tested Python
- **State is plain dicts** so it serialises straight to JSON in SQLite

## Known limitations

- Prompts haven't been tuned on real support data, and the 0.6 confidence threshold is a reasonable starting point rather than a measured one
- Escalation records a reason and status but doesn't notify anyone (no email, Slack or ticketing integration yet)
- Each ticket is processed independently, with no memory of the customer's earlier tickets
- Model-reported confidence is only a rough signal and isn't calibrated

## Ideas for next steps

- [ ] Human-in-the-loop approval step using LangGraph interrupts, so a person can approve drafts before they're sent
- [ ] Slack or email notification on escalation
- [ ] Retrieve past tickets and a knowledge base to ground the drafted reply
- [ ] A small FastAPI wrapper and dashboard
- [ ] Evaluate classification accuracy on a labelled ticket set

## Tech stack

Python · LangGraph · LangChain · OpenAI · Pydantic · SQLite · Pytest · GitHub Actions
