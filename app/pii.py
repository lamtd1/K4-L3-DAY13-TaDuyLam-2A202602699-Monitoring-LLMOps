from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "phone_vn": r"(?<!\d)(?:\+84|0084|0)(?:[ .-]?\d){9}(?!\d)",
    "passport": r"\b[A-Z]\d{7}\b",
    "api_key": r"(?i)\b(?:sk-[A-Za-z0-9_-]{20,}|api[_-]?key[=:]\s*[A-Za-z0-9._-]{16,})\b",
    "bearer_token": r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
