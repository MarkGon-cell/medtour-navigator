"""
Daily usage counters for the rate-limited Google AI search (2/day/user).

A counter table rather than an event log: the only question this needs to
answer, quickly and transactionally, is "how many of today's N uses are gone
for this user?". One row per (user, day) makes that a single indexed lookup,
and lets Postgres serialise concurrent first-use-of-the-day inserts with
SELECT ... FOR UPDATE / the unique constraint.

`user_key` is deliberately opaque: "user:<id>" when a bearer token resolved,
otherwise "device:<x-device-id>" or "ip:<address>" for guests (this app is
guest-first -- see docs/FRONTEND.md section 1).
"""

from sqlalchemy import Column, Date, Integer, String, UniqueConstraint

from app.database.database import Base


class GoogleSearchUsage(Base):
    __tablename__ = "google_search_usage"
    __table_args__ = (
        UniqueConstraint(
            "user_key",
            "usage_date",
            name="uq_google_search_usage_user_day",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Opaque quota owner, e.g. "user:7", "device:abc", "ip:10.0.0.4".
    user_key = Column(String, nullable=False, index=True)

    # The calendar day the counter belongs to (server local date).
    usage_date = Column(Date, nullable=False, index=True)

    # How many uses have been consumed today. Never exceeds the limit: the
    # quota check and the increment happen in one locked read-modify-write.
    used = Column(Integer, nullable=False, default=0, server_default="0")
