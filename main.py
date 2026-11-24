"""CLI: python main.py "My card was charged twice!" --customer alice"""
import argparse
import json
import os
import uuid

from triage.db import TicketStore
from triage.graph import build_graph, get_llm, triage_ticket
from triage.schemas import Ticket


def main():
    p = argparse.ArgumentParser(description="Triage a support ticket")
    p.add_argument("message")
    p.add_argument("--customer", default="anonymous")
    p.add_argument("--id", default=None)
    args = p.parse_args()

    store = TicketStore(os.getenv("TRIAGE_DB", "tickets.db"))
    graph = build_graph(get_llm(), store)
    ticket = Ticket(ticket_id=args.id or uuid.uuid4().hex[:8], customer=args.customer, message=args.message)
    print(json.dumps(triage_ticket(graph, ticket), indent=2))


if __name__ == "__main__":
    main()
