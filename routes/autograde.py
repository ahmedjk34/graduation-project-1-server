from __future__ import annotations

import urllib.request

from flask import Blueprint, jsonify, request

from autograde.grader import grade_submission
from rag.ocr_adapter import get_ocr_adapter
from rag.slide_ingest import (
    apply_ocr_to_slides,
    build_deck_text,
    load_pdf_slides,
    load_pptx,
)

autograde_bp = Blueprint("autograde", __name__)


def _download_bytes(
    url: str, *, max_bytes: int = 25 * 1024 * 1024, timeout_sec: float = 30.0
) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "autograde/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"File too large (> {max_bytes} bytes)")
    return data


def _extract_text_from_file_bytes(
    file_bytes: bytes, file_type: str, *, deck_id: str
) -> str:
    ocr_adapter = get_ocr_adapter()

    if file_type == "pdf":
        slides = load_pdf_slides(file_bytes, deck_id)
    elif file_type == "pptx":
        slides = load_pptx(file_bytes, deck_id)
    else:
        raise ValueError("Unsupported file type (expected pdf or pptx).")

    apply_ocr_to_slides(slides, ocr_adapter)
    return build_deck_text(slides)


@autograde_bp.route("/grade", methods=["POST"])
def autograde():
    #1. Check if the request is JSON; if not, return an error
    if not request.is_json:
        return jsonify({"error": "Request must be JSON."}), 400

    #2. Parse the JSON data from the request
    data = request.get_json(silent=True) or {}

    #3. Normalize and extract basic fields from the request data
    submission_id = str(data.get("submission_id") or "").strip()
    description = str(data.get("description") or "").strip()
    instructions = str(data.get("instructions") or "").strip()
    content = str(data.get("content") or "").strip()

    assignment_attachment_url = str(
        data.get("assignment_attachment_url")
        or data.get("assignment_url")
        or data.get("assignment_attachment")
        or ""
    ).strip()

    submission_attachment_url = str(
        data.get("submission_attachment_url")
        or data.get("submission_url")
        or data.get("submission_attachment")
        or data.get("attachment_url")
        or ""
    ).strip()

    #4. Validate required fields and collect errors
    errors = []

    try:
        max_points = int(data.get("max_points"))
        if max_points <= 0:
            errors.append("'max_points' must be > 0.")
    except Exception:
        errors.append("'max_points' is required and must be an integer.")

    if not submission_id:
        errors.append("'submission_id' is required.")

    if not (content or submission_attachment_url):
        errors.append("'content' and 'submission_attachment_url' cannot both be empty.")

    if not (assignment_attachment_url or description or instructions):
        errors.append(
            "'assignment_attachment_url', 'description', and 'instructions' cannot all be empty."
        )

    #5. If there are validation errors, return them
    if errors:
        return jsonify({"error": "Validation error.", "details": errors}), 400

    #6. Process assignment attachment if provided
    assignment_file_text = ""
    if assignment_attachment_url:
        try:
            #6a. Normalize the URL and add download parameter
            url = assignment_attachment_url.strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url.lstrip("/")

            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}download=assignment"

            #6b. Download the file bytes
            file_bytes = _download_bytes(url)
            head = file_bytes[:1024].lstrip()

            #6c. Determine file type based on header
            if head.startswith(b"%PDF"):
                file_type = "pdf"
            elif head.startswith(b"PK"):
                file_type = "pptx"
            else:
                return jsonify(
                    {"error": "Unsupported assignment attachment type (expected PDF or PPTX)."}
                ), 400

            #6d. Extract text from the file
            assignment_file_text = _extract_text_from_file_bytes(
                file_bytes,
                file_type,
                deck_id=f"assignment_{submission_id}",
            )
        except Exception as e:
            return jsonify(
                {"error": "Failed to process assignment attachment.", "details": str(e)}
            ), 502

    #7. Process submission attachment if provided
    submission_file_text = ""
    if submission_attachment_url:
        try:
            #7a. Normalize the URL and add download parameter
            url = submission_attachment_url.strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url.lstrip("/")

            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}download=submission"

            #7b. Download the file bytes
            file_bytes = _download_bytes(url)
            head = file_bytes[:1024].lstrip()

            #7c. Determine file type based on header
            if head.startswith(b"%PDF"):
                file_type = "pdf"
            elif head.startswith(b"PK"):
                file_type = "pptx"
            else:
                return jsonify(
                    {"error": "Unsupported submission attachment type (expected PDF or PPTX)."}
                ), 400

            #7d. Extract text from the file
            submission_file_text = _extract_text_from_file_bytes(
                file_bytes,
                file_type,
                deck_id=f"submission_{submission_id}",
            )
        except Exception as e:
            return jsonify(
                {"error": "Failed to process submission attachment.", "details": str(e)}
            ), 502

    #8. Build benchmark text from description, instructions, and assignment file text
    benchmark_parts = []
    if description:
        benchmark_parts.append(f"Description:\n{description}")
    if instructions:
        benchmark_parts.append(f"Instructions:\n{instructions}")
    if assignment_file_text:
        benchmark_parts.append(f"Assignment attachment:\n{assignment_file_text}")

    benchmark_text = "\n\n".join(benchmark_parts).strip()
    if not benchmark_text:
        return jsonify(
            {
                "error": "No assignment benchmark text available.",
                "details": (
                    "Provide at least one of: assignment attachment with extractable text, "
                    "'description', or 'instructions'."
                ),
            }
        ), 400

    #9. Build submission text from content and submission file text
    submission_parts = []
    if content:
        submission_parts.append(f"Submission content:\n{content}")
    if submission_file_text:
        submission_parts.append(f"Submission attachment:\n{submission_file_text}")

    submission_text = "\n\n".join(submission_parts).strip()
    if not submission_text:
        return jsonify(
            {
                "error": "No submission text available.",
                "details": (
                    "Provide at least one of: submission attachment with extractable text, "
                    "or 'content'."
                ),
            }
        ), 400

    #10. Perform grading using the grader function
    result = grade_submission(
        benchmark_text=benchmark_text,
        submission_text=submission_text,
        max_points=max_points,
        submission_id=submission_id,
    )

    #11. Check for errors in grading result and return appropriate response
    if "error" in result:
        return jsonify(result), 502 if result.get("details") else 500

    return jsonify(
        {"grade": result["grade"], "feedback": result["feedback"]}
    ), 200

