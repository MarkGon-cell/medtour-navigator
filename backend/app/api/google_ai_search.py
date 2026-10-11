"""
GET /ai/google-search -- Google AI Mode lookup, capped at 2 uses per user
per day.

Why a quota exists: this endpoint replays Google's private `async/folwr`
request from *our* servers (see app/services/google_ai_search.py). Every
real attempt costs us upstream goodwill and risks the egress IP, so the
allowance is deliberately tiny and enforced server-side -- a client that
hides its counter gains nothing.

Quota accounting:
  * 2/day by default (GOOGLE_AI_DAILY_LIMIT overrides it).
  * The key is the signed-in user id, else the client's X-Device-Id, else
    the caller's IP -- this app is guest-first, so most callers are guests.
  * A use is spent only when Google was actually contacted. The `link`
    fallback (no server session configured) makes no upstream request and
    therefore is free; a transport failure is refunded.
  * When the allowance is gone the endpoint still answers -- with
    `status: "limit"` and the AI Mode deep link -- because a quota should
    degrade a feature, not brick it.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_optional_current_user
from app.database.database import get_db
from app.models.user import User
from app.models.curated_hospital import CuratedHospital
from app.services import google_ai_search, rate_limit
from app.services.hospital_ai_enricher import enrich_curated_hospital_from_ai

router = APIRouter(
    prefix="/ai",
    tags=["Google AI Search"],
)

DAILY_LIMIT = int(os.getenv("GOOGLE_AI_DAILY_LIMIT", "2"))


def user_key(request: Request, user: Optional[User]) -> str:
    """
    Opaque quota owner.

    Signed-in users are stable across devices; guests fall back to a client
    supplied device id (set by the frontend) and finally to the IP, which is
    the only identity an unmodified client has.
    """
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"

    device = (request.headers.get("x-device-id") or "").strip()
    if 0 < len(device) <= 64:
        return f"device:{device}"

    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


@router.get("/google-search")
def google_ai_search_endpoint(
    request: Request,
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="What to ask Google AI about, e.g. a hospital name.",
    ),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_current_user),
):
    """
    One rate-limited Google AI Mode search.

    Response `status`:
      * `ok`      -- Google answered; `answer` + `sources` are filled in.
      * `limit`   -- today's 2 uses are spent; open `search_url` instead.
      * `link`    -- no server-side Google session configured; `search_url`
                     opens the same query in the user's own browser.
      * `blocked` / `unparsed` -- Google refused or the payload changed;
                     `search_url` still works and the use was spent because
                     our servers did contact Google.

    `usage` is always present so the UI can show "1 of 2 left today" before
    the user spends it.
    """
    key = user_key(request, user)
    snapshot = rate_limit.usage_snapshot(db, key, DAILY_LIMIT)

    if snapshot["remaining"] <= 0:
        return {
            "query": q,
            "status": "limit",
            "answer": "",
            "sources": [],
            "search_url": google_ai_search.ai_mode_url(q),
            "transport": "none",
            "detail": (
                f"Daily AI limit of {DAILY_LIMIT} reached. "
                "Your allowance resets at midnight."
            ),
            "usage": snapshot,
        }

    # Reserve before contacting Google: the check above is advisory, this is
    # the atomic one that stops two parallel clicks taking three uses.
    try:
        rate_limit.reserve(db, key, DAILY_LIMIT)
    except rate_limit.RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "usage": rate_limit.usage_snapshot(db, key, DAILY_LIMIT),
            },
        )

    try:
        result = google_ai_search.search(q)
    except google_ai_search.TransportError as exc:
        # Google was never reached -- hand the use back.
        rate_limit.release(db, key, DAILY_LIMIT)
        raise HTTPException(
            status_code=502,
            detail=f"Google could not be reached: {exc}",
        )

    if result["status"] == "link":
        # Nothing left our servers, so nothing was consumed.
        rate_limit.release(db, key, DAILY_LIMIT)
    hospital_db_info = None
    try:
        from app.models.hospital import Hospital
        # Try matching hospital by exact/partial query
        tokens = [t.strip() for t in q.split() if len(t.strip()) > 2]
        if tokens:
            hosp_match = db.query(Hospital).filter(Hospital.name.ilike(f"%{tokens[0]}%")).first()
            if hosp_match:
                hospital_db_info = {
                    "id": hosp_match.id,
                    "name": hosp_match.name,
                    "address": hosp_match.address,
                    "city": hosp_match.city,
                    "state": hosp_match.state,
                    "phone": hosp_match.phone,
                    "emergency_available": hosp_match.emergency_available,
                    "specialties": hosp_match.specialties,
                    "facilities": hosp_match.facilities,
                    "total_beds": hosp_match.total_beds,
                    "doctors": hosp_match.doctors,
                    "accreditation": hosp_match.accreditation,
                    "established_year": hosp_match.established_year,
                    "rating": hosp_match.rating,
                    "review_count": hosp_match.review_count,
                }
    except Exception as e:
        logger.warning(f"Failed to lookup hospital db record: {e}")

    nim_summary = None
    try:
        from app.api.hybrid_first_aid_retriever import nim_generate_json
        api_key = os.getenv("NVIDIA_NIM_API_KEY")
        if api_key and hospital_db_info:
            system_msg = (
                "You are an expert healthcare navigation assistant in India. "
                "Synthesize the provided hospital database record into a highly readable, patient-friendly summary layout.\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                '  "overview": "<2-sentence clear overview of the hospital and why it is trusted>",\n'
                '  "key_departments": ["<up to 4 primary departments>"],\n'
                '  "emergency_and_wait": "<clear statement on 24/7 ER availability, contact, and ambulance service>",\n'
                '  "patient_amenities": "<amenities, insurance cashless desk, bed capacity, doctors>",\n'
                '  "verdict": "<1 sentence final recommendation for patients/tourists>"\n'
                "}"
            )
            user_msg = f"HOSPITAL DATA:\n{json.dumps(hospital_db_info, ensure_ascii=False)}"
            gen = nim_generate_json(
                api_key=api_key,
                system_prompt=system_msg,
                user_message=user_msg,
                expect_key="overview",
                per_model_timeout=8.0,
                max_retries=1
            )
            if gen and isinstance(gen, dict) and gen.get("overview"):
                nim_summary = gen
    except Exception as e:
        logger.warning(f"NIM summary generation skipped or failed: {e}")

    return {
        "query": q,
        **result,
        "hospital_db_info": hospital_db_info,
        "nim_summary": nim_summary,
        "usage": rate_limit.usage_snapshot(db, key, DAILY_LIMIT),
    }
