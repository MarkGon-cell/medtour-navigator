"""
Reverse-engineered Google AI Mode (`udm=50`) search.

Verified behaviour (2026-10, probed from this repo):

  * `GET /search?q=...&udm=50` does NOT contain the AI answer. Google serves
    non-JS clients a ~93 kB JavaScript bootstrap shell instead (zero `<h3>`,
    zero organic links, a `<noscript>` retry marker). So scraping the SERP
    HTML gets nothing -- there is nothing to scrape.
  * The answer is delivered to the page by XHR, which is the request
    captured here:

        GET https://www.google.com/async/folwr?...&q=<query>&udm=50
            &async=_fmt:adl,_xsrf:<token>

    Parameters `srtst`, `garc`, `mlro`, `mlros` and the `_xsrf` inside
    `async` are minted per browser session, bound to that session's cookies,
    and carry an expiry (the captured `srtst` embeds `1791633409039`, i.e.
    mid-Oct 2026). Replaying them with fresh cookies returns **400**, which
    is why they live in `.env` and not in the repo.

So this module has two honest modes:

  1. `transport: "async"` -- the captured request replayed with the caller's
     own session material (env vars below). This is the only path that can
     return a real AI answer from our servers.
  2. `transport: "none"` -- no session material configured (or Google
     rejected it). We do not invent an answer: we return `status: "link"`
     with the same query's AI Mode URL (aimode.google.com), so the client
     opens it in the user's browser, where the session and JavaScript
     exist. The client does this automatically when the 2/day quota is
     spent too (`status: "limit"`), so the feature degrades to a hand-off
     instead of switching off.

Env (copy each value from DevTools > Network > `folwr` > Query, then reload
when Google rotates them -- roughly daily):

    GOOGLE_AI_COOKIE    full Cookie header (NID / __Secure-1PSIDTS / ...)
    GOOGLE_AI_SRTST     `srtst` query param
    GOOGLE_AI_GARC      `garc` query param
    GOOGLE_AI_MLRO      `mlro` query param
    GOOGLE_AI_MLROS     `mlros` query param
    GOOGLE_AI_XSRF      the `_xsrf` value inside the `async` param
    Optional: GOOGLE_AI_EI, GOOGLE_AI_VED, GOOGLE_AI_SCA_ESV,
              GOOGLE_AI_SOURCE (default "hp"), GOOGLE_AI_STKP,
              GOOGLE_AI_TIMEOUT (seconds, default 12)
"""

import json
import os
import re
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlencode

import requests

AI_MODE_URL = "https://www.google.com/search"

# Where a human lands when we hand the query off. Google's dedicated AI Mode
# host -- probed 200 alongside www.google.com/search?udm=50 (both serve the
# same JS bootstrap shell; aimode.google.com is the canonical entry point).
AI_MODE_DEEP_LINK = "https://aimode.google.com/search"

ASYNC_URL = "https://www.google.com/async/folwr"

# Browser-like, matching the capture (Google serves the JS shell to
# non-browser agents regardless, but the async endpoint checks the UA).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:158.0) "
    "Gecko/20100101 Firefox/158.0"
)

# Response markers that mean "Google is refusing", not "no answer".
_BLOCKED_MARKERS = (
    "unusual traffic",
    "consent.google.com",
    "our systems have detected",
    "please show you re not a robot",
)

# Boilerplate that must never be presented as an AI answer.
_DENYLIST = (
    "before you continue to google",
    "we use cookies",
    "accept all",
    "sign in to continue",
    "enable javascript",
)

_MAX_ANSWER_CHARS = 4000
_MAX_SOURCES = 8


class TransportError(Exception):
    """Google could not be reached at all (DNS/connect/timeout)."""


def ai_mode_url(query: str) -> str:
    """
    Deep link to the same query's AI Mode page, for the client to open.

    This is the hand-off URL: it is what the user's browser loads when the
    server cannot answer itself (no GOOGLE_AI_* session, or today's 2/day
    quota spent). `aimode.google.com` is the canonical AI Mode host.
    """
    return f"{AI_MODE_DEEP_LINK}?{urlencode({'q': query})}"


def _referer_url(query: str) -> str:
    """
    The `www.google.com/search?udm=50` form -- NOT the hand-off URL.

    The captured `async/folwr` request carried this as its Referer, so the
    replay must send the same shape back or Google sees an origin mismatch.
    """
    return f"{AI_MODE_URL}?{urlencode({'q': query, 'udm': '50', 'hl': 'en'})}"


def _configured() -> Dict[str, str]:
    """Session material present in the environment, if any."""
    required = {
        "cookie": os.getenv("GOOGLE_AI_COOKIE"),
        "srtst": os.getenv("GOOGLE_AI_SRTST"),
        "garc": os.getenv("GOOGLE_AI_GARC"),
        "mlro": os.getenv("GOOGLE_AI_MLRO"),
        "xsrf": os.getenv("GOOGLE_AI_XSRF"),
    }
    if not all(required.values()):
        return {}
    required["mlros"] = os.getenv("GOOGLE_AI_MLROS", "")
    return required


def _build_async_url(query: str, tokens: Dict[str, str]) -> str:
    """
    Rebuild the captured folwr request with `q` swapped in.

    Parameter order mirrors the capture; `safe=":,"` keeps `async=_fmt:adl,
    _xsrf:...` unencoded exactly as the browser sent it.
    """
    params: List[Tuple[str, str]] = [
        ("srtst", tokens["srtst"]),
        ("garc", tokens["garc"]),
        ("mlro", tokens["mlro"]),
    ]
    if tokens.get("mlros"):
        params.append(("mlros", tokens["mlros"]))
    if os.getenv("GOOGLE_AI_EI"):
        params.append(("ei", os.getenv("GOOGLE_AI_EI")))

    params.extend(
        [
            ("q", query),
            ("yv", "3"),
        ]
    )
    if os.getenv("GOOGLE_AI_VED"):
        params.append(("ved", os.getenv("GOOGLE_AI_VED")))
    params.append(("aep", "107"))
    params.append(("cs", "1"))
    if os.getenv("GOOGLE_AI_SCA_ESV"):
        params.append(("sca_esv", os.getenv("GOOGLE_AI_SCA_ESV")))
    params.append(("source", os.getenv("GOOGLE_AI_SOURCE", "hp")))
    params.append(("udm", "50"))
    if os.getenv("GOOGLE_AI_STKP"):
        params.append(("stkp", os.getenv("GOOGLE_AI_STKP")))
    params.append(("async", f"_fmt:adl,_xsrf:{tokens['xsrf']}"))

    return f"{ASYNC_URL}?{urlencode(params, safe=':,')}"


# ---------------------------------------------------------
# Response parsing
# ---------------------------------------------------------

_INITDATA_MARKER = "AF_initDataCallback("


def _iter_initdata_payloads(html: str) -> Iterator[str]:
    """
    Yield the object literal passed to every AF_initDataCallback(...).

    Google's data blobs are JavaScript, not JSON documents, so they cannot
    be regex-captured (nested braces). This walks the literal with a
    brace/string-aware scanner instead.
    """
    cursor = 0

    while True:
        marker_at = html.find(_INITDATA_MARKER, cursor)
        if marker_at < 0:
            return

        start = marker_at + len(_INITDATA_MARKER)
        depth = 0
        in_string = False
        quote = ""
        escaped = False
        end: Optional[int] = None

        for pos in range(start, len(html)):
            char = html[pos]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    in_string = False
                continue

            if char in "\"'":
                in_string = True
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = pos
                    break

        if end is None:
            return

        yield html[start : end + 1]
        cursor = end + 1


def _walk_strings(node) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_strings(value)


def _looks_like_prose(candidate: str) -> bool:
    if len(candidate) < 60:
        return False
    if any(marker in candidate.lower() for marker in _DENYLIST):
        return False
    if candidate.startswith(("http://", "https://", "//")):
        return False
    if any(char in candidate for char in "<{}\\"):
        return False
    if candidate.count(" ") < 8:
        return False

    letters = sum(char.isalpha() for char in candidate)
    return letters / len(candidate) > 0.6


def _source_url(candidate: str) -> Optional[str]:
    if not candidate.startswith(("http://", "https://")):
        return None
    if len(candidate) > 300 or " " in candidate:
        return None

    host = candidate.split("/", 3)[2].lower() if "//" in candidate else ""
    if not host:
        return None
    # Google's own plumbing is not a source.
    if host.endswith(("google.com", "googleusercontent.com", "gstatic.com")):
        return None
    return candidate


def _extract(html: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Pull the AI answer prose and outbound sources out of a folwr payload.

    Returns (answer, sources). The answer is every plausible prose string in
    payload order; sources are the non-Google URLs found alongside them.
    """
    answer_parts: List[str] = []
    sources: List[Dict[str, str]] = []
    seen_answers = set()
    seen_urls = set()
    seen_html_answers = set()

    for payload in _iter_initdata_payloads(html):
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            continue

        for text in _walk_strings(data):
            if _looks_like_prose(text) and text not in seen_answers:
                seen_answers.add(text)
                answer_parts.append(text[:1200])

            url = _source_url(text)
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(
                    {"title": url.split("/")[2], "url": url}
                )

    # Fallback: a rendered <h3> + link pair (present when Google does serve
    # real HTML, e.g. a consent-free datacenter exit).
    for title_html in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S):
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        if len(title) > 5 and title not in seen_html_answers:
            seen_html_answers.add(title)
            if len(answer_parts) < 6:
                answer_parts.append(title)

    answer = "\n\n".join(answer_parts).strip()
    if len(answer) > _MAX_ANSWER_CHARS:
        answer = answer[:_MAX_ANSWER_CHARS].rsplit(" ", 1)[0] + " ..."

    return answer, sources[:_MAX_SOURCES]


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

def search(query: str, timeout: Optional[float] = None) -> Dict[str, object]:
    """
    Run one Google AI Mode search.

    Returns::

        {
          "status": "ok" | "blocked" | "unparsed" | "link",
          "answer": str,          # status "ok" only
          "sources": [{"title", "url"}],
          "search_url": str,      # always: open this if status != ok
          "transport": "async" | "none",
          "detail": str,          # only when status != "ok"
        }

    Never raises for Google-side problems -- the caller still has to answer
    its quota question, and a dead Google must not become a 500.
    """
    query = (query or "").strip()
    search_url = ai_mode_url(query)
    timeout = timeout or float(os.getenv("GOOGLE_AI_TIMEOUT", "12"))

    tokens = _configured()
    if not tokens:
        return {
            "status": "link",
            "answer": "",
            "sources": [],
            "search_url": search_url,
            "transport": "none",
            "detail": (
                "No Google session configured on the server "
                "(GOOGLE_AI_* env vars); opening Google AI Mode instead."
            ),
        }

    url = _build_async_url(query, tokens)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": _referer_url(query),
        "Cookie": tokens["cookie"],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise TransportError(str(exc)) from exc

    body = response.text or ""

    if response.status_code != 200:
        return {
            "status": "blocked",
            "answer": "",
            "sources": [],
            "search_url": search_url,
            "transport": "async",
            "detail": (
                f"Google rejected the replayed request "
                f"(HTTP {response.status_code}); refresh the GOOGLE_AI_* "
                "tokens from DevTools."
            ),
        }

    lowered = body.lower()
    if any(marker in lowered for marker in _BLOCKED_MARKERS):
        return {
            "status": "blocked",
            "answer": "",
            "sources": [],
            "search_url": search_url,
            "transport": "async",
            "detail": "Google returned a challenge/consent page instead of results.",
        }

    answer, sources = _extract(body)

    if not answer:
        return {
            "status": "unparsed",
            "answer": "",
            "sources": sources,
            "search_url": search_url,
            "transport": "async",
            "detail": "Google answered, but no AI text could be parsed from it.",
        }

    return {
        "status": "ok",
        "answer": answer,
        "sources": sources,
        "search_url": search_url,
        "transport": "async",
    }
