#!/usr/bin/env python3
"""
Contract test for DOCX-first cover letter generation responses.

Validates these endpoints return:
  - markdown
  - docxTemplateHints
and do NOT return:
  - html
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Ensure project root is importable when run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth import get_current_user
from app.api.routers import cover_letter as cover_letter_router


def _mocked_get_job_info(**kwargs):
    # Include legacy html on purpose to verify router strips it.
    return {
        "markdown": "# Cover Letter\n\nDear Hiring Manager,",
        "html": "<h1>Cover Letter</h1><p>Dear Hiring Manager,</p>",
        "llmUsed": kwargs.get("llm"),
    }


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(cover_letter_router.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
    cover_letter_router.get_job_info = _mocked_get_job_info
    return TestClient(app)


def _assert_docx_contract(name: str, response):
    assert response.status_code == 200, f"{name}: expected 200, got {response.status_code}"
    data = response.json()
    assert "markdown" in data, f"{name}: missing markdown"
    assert "docxTemplateHints" in data, f"{name}: missing docxTemplateHints"
    assert "html" not in data, f"{name}: html should not be returned"
    return data


def run() -> int:
    client = _build_test_client()

    base_payload = {
        "llm": "gpt-4.1",
        "date_input": "2026-02-15",
        "company_name": "Example Co",
        "hiring_manager": "Alex Manager",
        "ad_source": "LinkedIn",
        "jd": "Job description text",
        "additional_instructions": "",
        "tone": "Professional",
        "address": "Las Vegas, NV",
        "phone_number": "555-555-5555",
        "user_id": "693326c07fcdaab8e81cdd2f",
        "user_email": "simon@example.com",
    }

    payload_job = {**base_payload, "resume": "Resume text"}
    payload_text_resume = {**base_payload, "resume_text": "Plain text resume"}
    payload_chat = {**base_payload, "resume": "Resume text"}

    checks = [
        ("job-info", "/api/job-info", payload_job),
        ("generate-with-text-resume", "/api/cover-letter/generate-with-text-resume", payload_text_resume),
        ("chat-job-info-route", "/api/chat", payload_chat),
    ]

    for name, path, payload in checks:
        resp = client.post(path, json=payload)
        data = _assert_docx_contract(name, resp)
        print(f"{name}: OK keys={sorted(data.keys())}")

    print("All DOCX response-contract checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
