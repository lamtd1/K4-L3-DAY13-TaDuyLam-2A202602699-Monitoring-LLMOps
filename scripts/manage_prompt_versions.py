"""Automate the day13-chat prompt versioning workflow from docs/PROMPT_VERSIONING.md.

Requires LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL for your
personal Langfuse Cloud project to be set (e.g. via `--env-file .env` or a
sourced .env). Uses the same three template variables the app expects:
Feature={{feature}} / Docs={{docs}} / Question={{message}}.

Usage:
    python scripts/manage_prompt_versions.py setup
    python scripts/manage_prompt_versions.py run --label baseline
    python scripts/manage_prompt_versions.py run --label candidate
    python scripts/manage_prompt_versions.py promote --version 2
    python scripts/manage_prompt_versions.py rollback --version 1
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from app.agent import LabAgent  # noqa: E402
from app.tracing import get_langfuse_client  # noqa: E402

PROMPT_NAME = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
V1_TEMPLATE = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
V2_TEMPLATE = (
    "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\n"
    "Answer in at most 3 concise sentences."
)


def cmd_setup(_: argparse.Namespace) -> None:
    client = get_langfuse_client()
    v1 = client.create_prompt(
        name=PROMPT_NAME,
        prompt=V1_TEMPLATE,
        labels=["baseline", "production"],
        type="text",
        commit_message="CP2: initial baseline/production prompt",
    )
    v2 = client.create_prompt(
        name=PROMPT_NAME,
        prompt=V2_TEMPLATE,
        labels=["candidate"],
        type="text",
        commit_message="CP2: candidate with a 3-sentence length constraint",
    )
    client.flush()
    print(f"Created {PROMPT_NAME} v{v1.version} labels=baseline,production")
    print(f"Created {PROMPT_NAME} v{v2.version} labels=candidate")


def cmd_run(args: argparse.Namespace) -> None:
    os.environ["LANGFUSE_PROMPT_LABEL"] = args.label
    correlation_id = f"req-{uuid.uuid4().hex[:8]}"
    agent = LabAgent()
    result = agent.run(
        user_id="prompt-versioning-check",
        feature="qa",
        session_id=f"prompt-check-{args.label}",
        message=args.message,
        correlation_id=correlation_id,
    )
    get_langfuse_client().flush()
    print(f"label={args.label} correlation_id={correlation_id}")
    print(f"answer_preview={result.answer[:80]!r}")
    print("Open Langfuse > Traces, filter by metadata.correlation_id to find this trace.")


def cmd_promote(args: argparse.Namespace) -> None:
    client = get_langfuse_client()
    client.update_prompt(name=PROMPT_NAME, version=args.version, new_labels=["production"])
    client.flush()
    print(f"{PROMPT_NAME} v{args.version} is now labeled production")


def cmd_rollback(args: argparse.Namespace) -> None:
    cmd_promote(args)
    print(f"Rollback complete: {PROMPT_NAME} production -> v{args.version}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Create v1 (baseline+production) and v2 (candidate)")

    run_parser = sub.add_parser("run", help="Run the agent against a given prompt label")
    run_parser.add_argument("--label", required=True, choices=["baseline", "candidate", "production"])
    run_parser.add_argument("--message", default="What is your refund policy?")

    promote_parser = sub.add_parser("promote", help="Point the production label at a version")
    promote_parser.add_argument("--version", type=int, required=True)

    rollback_parser = sub.add_parser("rollback", help="Alias for promote, used for rollback evidence")
    rollback_parser.add_argument("--version", type=int, required=True)

    args = parser.parse_args()
    handlers = {
        "setup": cmd_setup,
        "run": cmd_run,
        "promote": cmd_promote,
        "rollback": cmd_rollback,
    }
    handlers[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
