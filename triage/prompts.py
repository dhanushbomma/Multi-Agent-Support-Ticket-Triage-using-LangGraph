CLASSIFY = """You classify customer support tickets.
Categories: billing, technical, account, feature_request, other.

Ticket from {customer}:
{message}"""

PRIORITY = """You assess the priority of a support ticket.
- urgent: outage, data loss, security issue, legal threat
- high: blocked workflow, payment problem, very angry customer
- medium: degraded experience with a workaround
- low: questions, feedback, feature requests

Category: {category}
Ticket from {customer}:
{message}"""

DRAFT = """Write a polite, concise reply to this support ticket.
Do not promise refunds or timelines you cannot guarantee.

Category: {category}
Priority: {priority}
Ticket from {customer}:
{message}"""
