"""Explicit local review queue for feedback; ratings never train automatically."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CATEGORIES
from .contracts import analyze_plan, extract_category_from_effect, model_subset_issues, parse_json_document
from .dataset import load_dataset
from .paths import FEEDBACK_DIR, ensure_state_dirs

_FEEDBACK_ID_RE = re.compile(r"^feedback-[a-f0-9]{16}$")


def _path(feedback_id: str) -> Path:
    if not isinstance(feedback_id, str) or not _FEEDBACK_ID_RE.fullmatch(feedback_id):
        raise ValueError("Invalid feedback id.")
    return FEEDBACK_DIR / f"{feedback_id}.json"


def _write_record(record: dict[str, Any]) -> None:
    ensure_state_dirs()
    target = _path(record["id"])
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def create_feedback(
    generation: dict[str, Any],
    rating: str,
    notes: str = "",
    corrected_plan: Any = None,
    corrected_plan_text: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    if rating not in {"good", "poor", "invalid"}:
        raise ValueError("Rating must be good, poor, or invalid.")
    notes = str(notes)
    if len(notes) > 2000:
        raise ValueError("Feedback notes are limited to 2,000 characters.")
    prompt = generation.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1000:
        raise ValueError("The generation has no usable prompt.")

    chosen_category = category or generation.get("category") or ""
    candidate: Any = corrected_plan
    raw_plan: str | None = None
    parse_error: str | None = None
    if corrected_plan_text is not None:
        raw_plan = str(corrected_plan_text)
        candidate, parse_error = parse_json_document(raw_plan)
    elif candidate is None and rating == "good":
        candidate = generation.get("candidate_plan")
    if corrected_plan is not None and corrected_plan_text is None and not isinstance(corrected_plan, dict):
        try:
            raw_plan = json.dumps(corrected_plan, ensure_ascii=False)
        except (TypeError, ValueError):
            raw_plan = repr(corrected_plan)
        candidate = None

    if not chosen_category and isinstance(candidate, dict):
        chosen_category = extract_category_from_effect(candidate)
    if chosen_category not in CATEGORIES:
        chosen_category = ""

    plan_report = analyze_plan(candidate) if candidate is not None else {"ok": False, "issues": []}
    subset_issues = model_subset_issues(candidate) if plan_report["ok"] else []
    errors: list[str] = []
    if parse_error:
        errors.append(parse_error)
    if not plan_report["ok"] and candidate is not None:
        errors.extend(issue["message"] for issue in plan_report["issues"][:8])
    if subset_issues:
        errors.extend(issue["message"] for issue in subset_issues[:8])
    if not chosen_category:
        errors.append("Select a supported training category.")
    eligible = bool(candidate is not None and plan_report["ok"] and not subset_issues and chosen_category)

    feedback_id = f"feedback-{uuid.uuid4().hex[:16]}"
    record = {
        "id": feedback_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generation_id": generation.get("id"),
        "prompt": prompt,
        "rating": rating,
        "notes": notes,
        "category": chosen_category or None,
        "plan": candidate if isinstance(candidate, dict) else None,
        "raw_plan": raw_plan if candidate is None or not isinstance(candidate, dict) else None,
        "plan_valid": bool(plan_report["ok"]),
        "training_eligible": eligible,
        "eligibility_issues": errors,
        "approval_status": "pending",
        "trained_in": None,
    }
    _write_record(record)
    return record


def list_feedback() -> list[dict[str, Any]]:
    ensure_state_dirs()
    items: list[dict[str, Any]] = []
    for path in FEEDBACK_DIR.glob("feedback-*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            items.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    items.sort(key=lambda item: (item.get("created_at", ""), item.get("id", "")), reverse=True)
    return items


def approve_feedback(feedback_id: str, active_dataset: Path | None = None) -> dict[str, Any]:
    path = _path(feedback_id)
    if not path.is_file():
        raise FileNotFoundError(f"Feedback record not found: {feedback_id}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not record.get("training_eligible") or not record.get("plan_valid"):
        raise ValueError("This feedback has no valid plan in the model's supported subset; it cannot be approved for training.")
    if active_dataset is not None:
        active_records = load_dataset(active_dataset)
        if any(row["prompt"] == record["prompt"] for row in active_records):
            raise ValueError("This prompt already occurs in the active dataset. Do not add it as feedback training data because it could contaminate a held-out split.")
    approved_prompts = {item.get("prompt") for item in list_feedback() if item.get("approval_status") == "approved" and item.get("id") != feedback_id}
    if record["prompt"] in approved_prompts:
        raise ValueError("An approved feedback example already uses this exact prompt.")
    record["approval_status"] = "approved"
    record["approved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    _write_record(record)
    return record


def approved_training_records(base_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    known_prompts = {row["prompt"] for row in base_records}
    seen_feedback_prompts: set[str] = set()
    result: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for item in list_feedback():
        if item.get("approval_status") != "approved" or not item.get("training_eligible"):
            continue
        prompt = item.get("prompt")
        if prompt in known_prompts:
            skipped.append({"feedback_id": item["id"], "reason": "prompt overlaps the selected synthetic dataset; excluded to protect held-out splits"})
            continue
        if prompt in seen_feedback_prompts:
            skipped.append({"feedback_id": item["id"], "reason": "duplicate approved feedback prompt"})
            continue
        if item.get("category") not in CATEGORIES:
            skipped.append({"feedback_id": item["id"], "reason": "unsupported or missing category"})
            continue
        report = analyze_plan(item.get("plan"))
        if not report["ok"] or model_subset_issues(item.get("plan")):
            skipped.append({"feedback_id": item["id"], "reason": "plan no longer passes the supported plan-v1 checks"})
            continue
        seen_feedback_prompts.add(prompt)
        result.append(
            {
                "id": item["id"],
                "prompt": prompt,
                "category": item["category"],
                "plan": item["plan"],
                "split": "train",
                "group_id": f"reviewed-feedback:{item['id']}",
                "source": "human-approved-feedback",
                "seed": 0,
            }
        )
    return result, skipped
