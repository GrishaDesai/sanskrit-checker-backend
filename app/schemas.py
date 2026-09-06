from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Devanagari Sanskrit text to check")


class SyntaxIssueOut(BaseModel):
    token_index: int
    token_text: str
    issue_type: str
    title: str
    description: str
    suggested_text: str | None = None
    rule_sutra: str | None = None
    severity: str = "error"  # "error" (confirmed problem) | "review" (offered, not asserted)


class SamasaOut(BaseModel):
    compound_text: str
    compound_type: str
    vigraha_vakya: str
    components: list[str]


class TokenOut(BaseModel):
    text: str
    lemma: str | None = None
    is_valid: bool
    status: str = "valid"  # "valid" | "invalid" | "sandhi_error" | "karaka_error" | "agreement_error"
    severity: str = "error"  # "error" (confirmed problem) | "review" (offered, not asserted)
    analysis: str | None = None
    suggestion: str | None = None
    rule: str | None = None
    sandhi_issue: str | None = None
    karaka_issue: str | None = None


class CheckResponse(BaseModel):
    input_text: str
    tokens: list[TokenOut]
    error_count: int
    review_count: int = 0
    sandhi_error_count: int = 0
    syntax_error_count: int = 0
    syntax_issues: list[SyntaxIssueOut] = []
    compounds: list[SamasaOut] = []
    token_count: int
