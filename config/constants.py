"""Project-wide enums, routing rules, escalation keywords, and generation constants."""
from enum import Enum


# ── Ticket Classification ─────────────────────────────────────────────────────

class TicketCategory(str, Enum):
    BILLING = "Billing"
    REFUND = "Refund"
    TECHNICAL_SUPPORT = "Technical Support"
    ACCOUNT_ACCESS = "Account Access"
    PRODUCT_QUESTIONS = "Product Questions"
    GENERAL_INQUIRY = "General Inquiry"


# ── Routing Departments ───────────────────────────────────────────────────────

class Department(str, Enum):
    BILLING_TEAM = "Billing Team"
    TECHNICAL_SUPPORT_TEAM = "Technical Support Team"
    CUSTOMER_SUCCESS_TEAM = "Customer Success Team"
    PRODUCT_TEAM = "Product Team"
    HUMAN_REVIEW_QUEUE = "Human Review Queue"


# ── Ticket Channels ───────────────────────────────────────────────────────────

class TicketChannel(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    API = "api"


# ── Ticket Priority ───────────────────────────────────────────────────────────

class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Default Routing Rules ─────────────────────────────────────────────────────
# Maps each ticket category to its default handling department.
# The agent can override this based on context.

CATEGORY_TO_DEPARTMENT: dict[str, str] = {
    TicketCategory.BILLING: Department.BILLING_TEAM,
    TicketCategory.REFUND: Department.BILLING_TEAM,
    TicketCategory.TECHNICAL_SUPPORT: Department.TECHNICAL_SUPPORT_TEAM,
    TicketCategory.ACCOUNT_ACCESS: Department.TECHNICAL_SUPPORT_TEAM,
    TicketCategory.PRODUCT_QUESTIONS: Department.PRODUCT_TEAM,
    TicketCategory.GENERAL_INQUIRY: Department.CUSTOMER_SUCCESS_TEAM,
}


# ── Escalation Trigger Keywords ───────────────────────────────────────────────
# If any of these appear in the ticket message, escalation is forced
# regardless of the confidence score.

ESCALATION_KEYWORDS: list[str] = [
    "legal",
    "lawsuit",
    "lawyer",
    "attorney",
    "court",
    "compliance",
    "fraud",
    "unauthorized charge",
    "data breach",
    "privacy violation",
    "gdpr",
    "threatening",
    "discrimination",
    "harassment",
]


# ── LLM Generation Config ─────────────────────────────────────────────────────

TEMPERATURE = 0.2           # Low = consistent, factual responses
MAX_RESPONSE_TOKENS = 1024  # Max tokens for customer-facing response
MAX_SUMMARY_TOKENS = 256    # Max tokens for ticket summary


# ── RAG Config ────────────────────────────────────────────────────────────────

CHUNK_SIZE = 500            # Characters per document chunk
CHUNK_OVERLAP = 50          # Overlap between chunks to preserve context


# ── Policy Document Sources ───────────────────────────────────────────────────
# Maps ticket categories to the policy files most relevant to that category.

CATEGORY_TO_POLICY_FILES: dict[str, list[str]] = {
    TicketCategory.BILLING: ["billing_policy.md", "support_faq.md"],
    TicketCategory.REFUND: ["refund_policy.md", "billing_policy.md"],
    TicketCategory.TECHNICAL_SUPPORT: ["technical_support_guide.md", "support_faq.md"],
    TicketCategory.ACCOUNT_ACCESS: ["technical_support_guide.md", "support_faq.md"],
    TicketCategory.PRODUCT_QUESTIONS: ["support_faq.md", "technical_support_guide.md"],
    TicketCategory.GENERAL_INQUIRY: ["support_faq.md"],
}
