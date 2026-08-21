"""Thin Jira REST client — count-first, field-minimal queries."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

_session: httpx.Client | None = None
_cache: dict[str, Any] = {}


def _get_session() -> httpx.Client:
    global _session
    if _session is None:
        base_url = os.environ["JIRA_URL"]
        email = os.environ["JIRA_EMAIL"]
        token = os.environ["JIRA_TOKEN"]
        _session = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(email, token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )
    return _session


def _deployment() -> str:
    return os.environ.get("JIRA_DEPLOYMENT", "cloud")


def count(jql: str) -> int:
    """Return issue count for a JQL query. No issue data fetched."""
    cache_key = f"count:{jql}"
    if cache_key in _cache:
        return _cache[cache_key]

    client = _get_session()

    if _deployment() == "cloud":
        resp = client.post(
            "/rest/api/3/search/approximate-count",
            json={"jql": jql},
        )
        resp.raise_for_status()
        result = resp.json().get("count", 0)
    else:
        resp = client.get(
            "/rest/api/2/search",
            params={"jql": jql, "maxResults": 0},
        )
        resp.raise_for_status()
        result = resp.json().get("total", 0)

    _cache[cache_key] = result
    return result


def search(jql: str, fields: list[str], max_results: int = 100) -> list[dict]:
    """Fetch issues with minimal fields. Use sparingly — prefer count()."""
    cache_key = f"search:{jql}:{','.join(sorted(fields))}:{max_results}"
    if cache_key in _cache:
        return _cache[cache_key]

    client = _get_session()
    issues: list[dict] = []
    start_at = 0

    while True:
        page_size = min(max_results - len(issues), 100)
        if _deployment() == "cloud":
            resp = client.get(
                "/rest/api/3/search/jql",
                params={
                    "jql": jql,
                    "fields": ",".join(fields),
                    "maxResults": page_size,
                    "startAt": start_at,
                },
            )
        else:
            resp = client.get(
                "/rest/api/2/search",
                params={
                    "jql": jql,
                    "fields": ",".join(fields),
                    "maxResults": page_size,
                    "startAt": start_at,
                },
            )

        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        total = data.get("total", 0)
        issues.extend(batch)

        if len(batch) == 0 or len(issues) >= max_results or len(issues) >= total:
            break
        start_at += len(batch)

    _cache[cache_key] = issues
    return issues


def get_confluence_remote_links(issue_key: str) -> list[dict]:
    """Fetch Jira's 'Confluence content' backlinks for an issue — the pages Jira
    itself has detected as referencing this issue (the same data the issue's
    Confluence content panel shows). Returns [{"title", "url", "page_id"}].
    """
    cache_key = f"remotelink:{issue_key}"
    if cache_key in _cache:
        return _cache[cache_key]

    client = _get_session()
    resp = client.get(f"/rest/api/3/issue/{issue_key}/remotelink")
    resp.raise_for_status()

    links: list[dict] = []
    for item in resp.json():
        if item.get("application", {}).get("type") != "com.atlassian.confluence":
            continue
        obj = item.get("object", {})
        title = obj.get("title", "")
        url = obj.get("url", "")
        if not (title and url):
            continue
        global_id = item.get("globalId", "")
        page_id = global_id.split("pageId=")[-1] if "pageId=" in global_id else ""
        links.append({"title": title, "url": url, "page_id": page_id})

    _cache[cache_key] = links
    return links


def get_rendered_description(issue_key: str) -> str:
    """Fetch a single issue's description rendered as HTML, or "" if empty.

    Used only as a raw-excerpt fallback (verbatim source text, not a generated
    summary) when no linked Confluence page exists to excerpt from instead.
    """
    cache_key = f"rendered_desc:{issue_key}"
    if cache_key in _cache:
        return _cache[cache_key]

    client = _get_session()
    resp = client.get(
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": "description", "expand": "renderedFields"},
    )
    resp.raise_for_status()
    html = resp.json().get("renderedFields", {}).get("description", "") or ""

    _cache[cache_key] = html
    return html


def get_issue_changelog(issue_key: str) -> list[dict]:
    """Fetch changelog for a single issue (needed for time-in-status)."""
    cache_key = f"changelog:{issue_key}"
    if cache_key in _cache:
        return _cache[cache_key]

    client = _get_session()
    histories: list[dict] = []
    start_at = 0

    while True:
        if _deployment() == "cloud":
            resp = client.get(
                f"/rest/api/3/issue/{issue_key}/changelog",
                params={"startAt": start_at, "maxResults": 100},
            )
        else:
            resp = client.get(
                f"/rest/api/2/issue/{issue_key}",
                params={"expand": "changelog", "fields": "none"},
            )

        resp.raise_for_status()
        data = resp.json()

        if _deployment() == "cloud":
            batch = data.get("values", [])
            histories.extend(batch)
            if data.get("isLast", True):
                break
            start_at += len(batch)
        else:
            histories = data.get("changelog", {}).get("histories", [])
            break

    _cache[cache_key] = histories
    return histories


def clear_cache() -> None:
    """Clear the query cache (call between pipeline runs if reused)."""
    _cache.clear()


def close() -> None:
    """Close the HTTP session."""
    global _session
    if _session:
        _session.close()
        _session = None
