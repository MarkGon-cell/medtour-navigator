"""
Daily per-user quotas.

Used by GET /ai/google-search to hold callers to 2 AI answers per day. The
same helper would serve any other daily allowance -- nothing here knows what
is being counted.

Semantics:
  * `reserve()` refuses once today's row reaches the limit and increments it
    otherwise, in one locked read-modify-write so two parallel requests
    cannot both take the last use.
  * `release()` gives a reserved use back. Callers refund only when the
    upstream was never reached (transport error) or when nothing was
    delivered server-side; a rejected Google request still costs the use, or
    a caller could retry our proxy against Google an unlimited number of
    times.
  * `usage_snapshot()` is the read-only view returned to clients so the UI
    can show "1 of 2 left today" before the user spends it.
"""

from datetime import date
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.google_search_usage import GoogleSearchUsage


class RateLimitExceeded(Exception):
    """Raised by `reserve()` when the daily allowance is already spent."""

    def __init__(self, limit: int, used: int, resets_on: date):
        self.limit = limit
        self.used = used
        self.resets_on = resets_on
        super().__init__(
            f"Daily limit of {limit} reached; resets on {resets_on.isoformat()}"
        )


def _find_row(
    db: Session,
    user_key: str,
    usage_date: date,
    lock: bool,
) -> Optional[GoogleSearchUsage]:
    query = db.query(GoogleSearchUsage).filter(
        GoogleSearchUsage.user_key == user_key,
        GoogleSearchUsage.usage_date == usage_date,
    )
    # SQLite ignores FOR UPDATE (single-writer anyway); Postgres serialises
    # concurrent reserves for the same (user, day) row.
    return query.with_for_update().first() if lock else query.first()


def usage_snapshot(
    db: Session,
    user_key: str,
    limit: int,
    usage_date: Optional[date] = None,
) -> dict:
    """Read-only {limit, used, remaining, date} for a user."""
    usage_date = usage_date or date.today()
    row = _find_row(db, user_key, usage_date, lock=False)
    used = row.used if row else 0

    return {
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "date": usage_date.isoformat(),
    }


def reserve(
    db: Session,
    user_key: str,
    limit: int,
    usage_date: Optional[date] = None,
) -> dict:
    """
    Claim one use for today.

    Returns the post-increment snapshot. Raises `RateLimitExceeded` without
    consuming anything when the allowance is already gone.
    """
    usage_date = usage_date or date.today()
    row = _find_row(db, user_key, usage_date, lock=True)

    if row is None:
        row = GoogleSearchUsage(
            user_key=user_key,
            usage_date=usage_date,
            used=0,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Lost the race to create today's row -- reload the winner's.
            db.rollback()
            row = _find_row(db, user_key, usage_date, lock=True)
            if row is None:
                raise

    if row.used >= limit:
        raise RateLimitExceeded(limit, row.used, usage_date)

    row.used += 1
    db.commit()

    return usage_snapshot(db, user_key, limit, usage_date)


def release(
    db: Session,
    user_key: str,
    limit: int,
    usage_date: Optional[date] = None,
) -> dict:
    """Give a reserved use back (never below zero)."""
    usage_date = usage_date or date.today()
    row = _find_row(db, user_key, usage_date, lock=True)

    if row is not None and row.used > 0:
        row.used -= 1
        db.commit()

    return usage_snapshot(db, user_key, limit, usage_date)
