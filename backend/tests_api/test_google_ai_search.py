"""
Unit tests for the rate-limited Google AI search.

    python tests_api/test_google_ai_search.py

Covers the two halves that must not regress:

1. The 2-uses/day quota: reserve/refund accounting, per-user isolation and
   the midnight reset. A quota that leaks is worse than no quota -- callers
   trust it to be exact.
2. The reverse-engineered folwr transport: query-string shape, the
   brace-aware AF_initDataCallback scanner, prose/source extraction, and the
   honest fallbacks (no session -> `link`, Google -> `blocked`) instead of a
   fabricated answer.

No live Google call is made: `requests.get` is stubbed where the network
would otherwise be involved.
"""

import json
import os
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.google_ai_search import user_key
from app.database.database import Base
from app.models.google_search_usage import GoogleSearchUsage
from app.services import google_ai_search, rate_limit

failures: list[str] = []

LIMIT = 2
KEY = "ip:10.0.0.4"


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} -- {detail}")
        failures.append(label)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------

def test_two_uses_per_day():
    db = make_session()

    first = rate_limit.reserve(db, KEY, LIMIT)
    check("first use allowed", first["used"] == 1 and first["remaining"] == 1, f"got {first}")

    second = rate_limit.reserve(db, KEY, LIMIT)
    check("second use allowed", second["used"] == 2 and second["remaining"] == 0, f"got {second}")

    try:
        rate_limit.reserve(db, KEY, LIMIT)
        check("third use rejected", False, "no RateLimitExceeded raised")
    except rate_limit.RateLimitExceeded as exc:
        check(
            "third use rejected",
            exc.limit == LIMIT,
            f"got {exc}",
        )

    snapshot = rate_limit.usage_snapshot(db, KEY, LIMIT)
    check(
        "rejected reserve consumed nothing",
        snapshot["used"] == 2 and snapshot["remaining"] == 0,
        f"got {snapshot}",
    )
    db.close()


def test_release_gives_a_use_back():
    db = make_session()

    rate_limit.reserve(db, KEY, LIMIT)
    rate_limit.reserve(db, KEY, LIMIT)

    refunded = rate_limit.release(db, KEY, LIMIT)
    check("release decrements", refunded["used"] == 1 and refunded["remaining"] == 1, f"got {refunded}")

    # Never runs the counter negative, even if called without a reservation.
    rate_limit.release(db, KEY, LIMIT)
    floored = rate_limit.release(db, KEY, LIMIT)
    check("release floors at zero", floored["used"] == 0, f"got {floored}")

    # A refunded use is usable again.
    again = rate_limit.reserve(db, KEY, LIMIT)
    check("refunded use can be spent", again["used"] == 1, f"got {again}")
    db.close()


def test_quota_is_per_user_and_per_day():
    db = make_session()

    rate_limit.reserve(db, "ip:1.1.1.1", LIMIT)
    rate_limit.reserve(db, "ip:1.1.1.1", LIMIT)

    other_user = rate_limit.usage_snapshot(db, "ip:2.2.2.2", LIMIT)
    check(
        "another user starts fresh",
        other_user["used"] == 0 and other_user["remaining"] == LIMIT,
        f"got {other_user}",
    )

    tomorrow = rate_limit.usage_snapshot(
        db, "ip:1.1.1.1", LIMIT, usage_date=date(2099, 1, 2)
    )
    check(
        "next day resets the counter",
        tomorrow["used"] == 0 and tomorrow["remaining"] == LIMIT,
        f"got {tomorrow}",
    )
    db.close()


def test_user_key_prefers_signed_in_user():
    request = SimpleNamespace(
        headers={"x-device-id": "device-abc"},
        client=SimpleNamespace(host="203.0.113.9"),
    )

    signed_in = SimpleNamespace(id=42)
    check(
        "signed-in user key wins",
        user_key(request, signed_in) == "user:42",
        f"got {user_key(request, signed_in)}",
    )
    check(
        "guests fall back to the device id",
        user_key(request, None) == "device:device-abc",
        f"got {user_key(request, None)}",
    )

    no_device = SimpleNamespace(
        headers={},
        client=SimpleNamespace(host="203.0.113.9"),
    )
    check(
        "no device id falls back to the IP",
        user_key(no_device, None) == "ip:203.0.113.9",
        f"got {user_key(no_device, None)}",
    )


# ---------------------------------------------------------
# Transport
# ---------------------------------------------------------

def _payload_html() -> str:
    """The shape folwr returns: AF_initDataCallback wrapping JSON data."""
    data = [
        [
            "Palladium Janseva Multispeciality Hospital is a multispeciality "
            "facility in Vasai West offering cardiology, orthopaedics and "
            "24x7 emergency care, with inpatient beds and diagnostic imaging "
            "on site.",
            "https://example.org/palladium-janseva",
            "https://www.google.com/jsproxy",
        ]
    ]
    payload = json.dumps({"key": "ds:5", "hash": "abc", "data": data})
    return f"<html><script>AF_initDataCallback({payload});</script></html>"


def test_extract_pulls_prose_and_sources():
    html = _payload_html()
    answer, sources = google_ai_search._extract(html)

    check(
        "answer prose extracted",
        "multispeciality facility" in answer,
        f"got {answer[:80]!r}",
    )
    check(
        "external source kept",
        any(s["url"].startswith("https://example.org/") for s in sources),
        f"got {sources}",
    )
    check(
        "google plumbing dropped as a source",
        not any("google.com" in s["url"] for s in sources),
        f"got {sources}",
    )


def test_scanner_survives_nested_braces_and_strings():
    inner = json.dumps({"note": "a } brace and a \" quote", "url": "https://x.test/a"})
    payload = json.dumps({"key": "ds:9", "data": [[inner, "A sentence long enough to count as prose maybe, with plenty of words here."]]})
    html = f"<script>AF_initDataCallback({payload});</script>"

    payloads = list(google_ai_search._iter_initdata_payloads(html))
    check("scanner yields one balanced payload", len(payloads) == 1, f"got {len(payloads)}")

    parsed = json.loads(payloads[0]) if payloads else None
    check(
        "scanner payload round-trips as JSON",
        parsed is not None and parsed.get("key") == "ds:9",
        f"got {payloads[:1]!r}",
    )


def test_no_session_returns_link_not_a_fabricated_answer():
    for name in (
        "GOOGLE_AI_COOKIE",
        "GOOGLE_AI_SRTST",
        "GOOGLE_AI_GARC",
        "GOOGLE_AI_MLRO",
        "GOOGLE_AI_XSRF",
    ):
        os.environ.pop(name, None)

    result = google_ai_search.search("Lilavati Heart Institute")

    check("no session -> status link", result["status"] == "link", f"got {result['status']}")
    check("link mode does not invent an answer", result["answer"] == "", f"got {result['answer']!r}")
    check(
        "link points at AI Mode for this exact query",
        "aimode.google.com/search?q=" in result["search_url"]
        and "Lilavati" in result["search_url"],
        f"got {result['search_url']}",
    )
    check("link mode makes no upstream call", result["transport"] == "none", f"got {result['transport']}")


def test_async_url_replays_the_captured_shape():
    tokens = {
        "cookie": "NID=abc",
        "srtst": "token:1791633409039",
        "garc": "garc-value",
        "mlro": "mlro-value",
        "mlros": "mlros-value",
        "xsrf": "xsrf-token",
    }
    url = google_ai_search._build_async_url("KEM Hospital", tokens)

    check(
        "async URL targets /async/folwr",
        url.startswith("https://www.google.com/async/folwr?"),
        f"got {url}",
    )
    check(
        "async URL carries the captured params",
        all(
            part in url
            for part in (
                # The capture sends srtst with a raw ':' before its expiry
                # timestamp -- encoding it is what a naive urlencode does.
                "srtst=token:1791633409039",
                "garc=garc-value",
                "mlro=mlro-value",
                "q=KEM+Hospital",
                "udm=50",
            )
        ),
        f"got {url}",
    )
    check(
        "async param keeps its _fmt:adl,_xsrf: shape unencoded",
        "_fmt:adl,_xsrf:xsrf-token" in url,
        f"got {url}",
    )


def test_handoff_url_and_replay_referer_are_different_shapes():
    """
    The user-facing hand-off went to aimode.google.com; the replay's Referer
    must keep the captured www.google.com/search?udm=50 shape, because that
    is the origin Google saw the folwr request come from.
    """
    handoff = google_ai_search.ai_mode_url("Asian Heart Institute")
    referer = google_ai_search._referer_url("Asian Heart Institute")

    check(
        "hand-off points at the AI Mode host",
        handoff.startswith("https://aimode.google.com/search?q=")
        and "Asian+Heart+Institute" in handoff,
        f"got {handoff}",
    )
    check(
        "hand-off carries no udm param",
        "udm" not in handoff,
        f"got {handoff}",
    )
    check(
        "replay Referer keeps the captured shape",
        referer.startswith("https://www.google.com/search?")
        and "udm=50" in referer,
        f"got {referer}",
    )

    # And search() must actually send that Referer, not the hand-off URL.
    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs.get("headers") or {})
        return SimpleNamespace(status_code=400, text="")

    saved_env = {
        name: os.environ.get(name)
        for name in ("GOOGLE_AI_COOKIE", "GOOGLE_AI_SRTST", "GOOGLE_AI_GARC", "GOOGLE_AI_MLRO", "GOOGLE_AI_XSRF")
    }
    os.environ.update(
        {
            "GOOGLE_AI_COOKIE": "NID=abc",
            "GOOGLE_AI_SRTST": "s",
            "GOOGLE_AI_GARC": "g",
            "GOOGLE_AI_MLRO": "m",
            "GOOGLE_AI_XSRF": "x",
        }
    )

    original = google_ai_search.requests.get
    google_ai_search.requests.get = fake_get
    try:
        google_ai_search.search("KEM Hospital")
        sent_referer = captured.get("Referer", "")
        check(
            "outbound replay sends the captured-shape Referer",
            sent_referer.startswith("https://www.google.com/search?")
            and "udm=50" in sent_referer,
            f"got {sent_referer!r}",
        )
    finally:
        google_ai_search.requests.get = original
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_rejected_replay_is_blocked_not_ok():
    original = google_ai_search.requests.get

    def fake_get(*args, **kwargs):
        return SimpleNamespace(status_code=400, text="")

    saved_env = {
        name: os.environ.get(name)
        for name in ("GOOGLE_AI_COOKIE", "GOOGLE_AI_SRTST", "GOOGLE_AI_GARC", "GOOGLE_AI_MLRO", "GOOGLE_AI_XSRF")
    }
    os.environ.update(
        {
            "GOOGLE_AI_COOKIE": "NID=abc",
            "GOOGLE_AI_SRTST": "s",
            "GOOGLE_AI_GARC": "g",
            "GOOGLE_AI_MLRO": "m",
            "GOOGLE_AI_XSRF": "x",
        }
    )

    google_ai_search.requests.get = fake_get
    try:
        result = google_ai_search.search("KEM Hospital")
        check(
            "HTTP 400 from Google -> status blocked",
            result["status"] == "blocked",
            f"got {result['status']}",
        )
        check(
            "blocked response still offers the deep link",
            "aimode.google.com/search?q=" in result["search_url"],
            f"got {result['search_url']}",
        )
        check(
            "blocked response explains itself",
            bool(result.get("detail")),
            "missing detail",
        )
    finally:
        google_ai_search.requests.get = original
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_ok_replay_returns_the_answer():
    original = google_ai_search.requests.get

    def fake_get(*args, **kwargs):
        return SimpleNamespace(status_code=200, text=_payload_html())

    saved_env = {
        name: os.environ.get(name)
        for name in ("GOOGLE_AI_COOKIE", "GOOGLE_AI_SRTST", "GOOGLE_AI_GARC", "GOOGLE_AI_MLRO", "GOOGLE_AI_XSRF")
    }
    os.environ.update(
        {
            "GOOGLE_AI_COOKIE": "NID=abc",
            "GOOGLE_AI_SRTST": "s",
            "GOOGLE_AI_GARC": "g",
            "GOOGLE_AI_MLRO": "m",
            "GOOGLE_AI_XSRF": "x",
        }
    )

    google_ai_search.requests.get = fake_get
    try:
        result = google_ai_search.search("Palladium Janseva Multispeciality Hospital")
        check("successful replay -> status ok", result["status"] == "ok", f"got {result['status']}")
        check(
            "answer text returned",
            "multispeciality facility" in result["answer"],
            f"got {result['answer'][:80]!r}",
        )
        check(
            "sources returned",
            any("example.org" in s["url"] for s in result["sources"]),
            f"got {result['sources']}",
        )
    finally:
        google_ai_search.requests.get = original
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main():
    test_two_uses_per_day()
    test_release_gives_a_use_back()
    test_quota_is_per_user_and_per_day()
    test_user_key_prefers_signed_in_user()
    test_extract_pulls_prose_and_sources()
    test_scanner_survives_nested_braces_and_strings()
    test_no_session_returns_link_not_a_fabricated_answer()
    test_handoff_url_and_replay_referer_are_different_shapes()
    test_async_url_replays_the_captured_shape()
    test_rejected_replay_is_blocked_not_ok()
    test_ok_replay_returns_the_answer()

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        sys.exit(1)
    print("ALL GOOGLE AI SEARCH TESTS PASSED")


if __name__ == "__main__":
    main()
