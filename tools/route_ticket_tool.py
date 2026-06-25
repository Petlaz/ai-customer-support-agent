"""route_ticket_tool — LangChain tool that maps a ticket category to a department.

A pure lookup against CATEGORY_TO_DEPARTMENT — no LLM call, no I/O.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from config.constants import CATEGORY_TO_DEPARTMENT, Department

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RouteTicketInput(BaseModel):
    classification: str = Field(
        ...,
        description="Ticket category, e.g. 'Billing', 'Technical Support'",
    )


class RouteTicketOutput(BaseModel):
    department: str = Field(description="Department name to handle this ticket")
    routing_reason: str = Field(description="Explanation of why this department was chosen")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def route_ticket(classification: str) -> dict:
    """Map a ticket classification to the appropriate handling department.

    Returns the department name and a short routing reason.
    Defaults to Customer Success Team for unknown categories.
    """
    department = CATEGORY_TO_DEPARTMENT.get(
        classification,
        Department.CUSTOMER_SUCCESS_TEAM,
    )
    dept_value = department.value if hasattr(department, "value") else str(department)
    reason = f"Category '{classification}' is handled by {dept_value}."
    logger.info("route_ticket: '%s' → '%s'.", classification, dept_value)
    return RouteTicketOutput(
        department=dept_value,
        routing_reason=reason,
    ).model_dump()
