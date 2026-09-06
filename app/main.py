import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.sanskrit_engine import SanskritEngine
from app.schemas import (
    CheckRequest,
    CheckResponse,
    TokenOut,
    SyntaxIssueOut,
    SamasaOut,
)

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VIDYUT_DATA_DIR = BASE_DIR / "vidyut-data"

app = FastAPI(title="Sanskrit Proof-Checker API (Phase 1, 2 & 3)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: SanskritEngine | None = None


@app.on_event("startup")
def load_engine():
    global engine
    engine = SanskritEngine(VIDYUT_DATA_DIR)


@app.get("/api/health")
def health():
    return {"status": "ok", "engine_loaded": engine is not None}


@app.post("/api/check", response_model=CheckResponse)
def check_text(payload: CheckRequest):
    global engine
    if engine is None:
        load_engine()

    result = engine.check_text(payload.text)

    return CheckResponse(
        input_text=result.input_text,
        tokens=[
            TokenOut(
                text=t.text_deva,
                lemma=t.lemma,
                is_valid=t.is_valid,
                status=t.status,
                severity=t.severity,
                analysis=t.analysis,
                suggestion=t.suggestion,
                rule=t.rule,
                sandhi_issue=t.sandhi_issue,
                karaka_issue=t.karaka_issue,
            )
            for t in result.tokens
        ],
        error_count=result.error_count,
        review_count=result.review_count,
        sandhi_error_count=result.sandhi_error_count,
        syntax_error_count=result.syntax_error_count,
        syntax_issues=[
            SyntaxIssueOut(
                token_index=issue.token_index,
                token_text=issue.token_text,
                issue_type=issue.issue_type,
                title=issue.title,
                description=issue.description,
                suggested_text=issue.suggested_text,
                rule_sutra=issue.rule_sutra,
                severity=issue.severity,
            )
            for issue in result.syntax_issues
        ],
        compounds=[
            SamasaOut(
                compound_text=c.compound_text,
                compound_type=c.compound_type,
                vigraha_vakya=c.vigraha_vakya,
                components=c.components,
            )
            for c in result.compounds
        ],
        token_count=len(result.tokens),
    )
