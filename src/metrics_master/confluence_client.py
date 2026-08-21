"""Confluence REST client — child page create/update + attachment upload."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = Path(".state.json")
_session: httpx.Client | None = None


def _get_session() -> httpx.Client:
    global _session
    if _session is None:
        base_url = os.environ["CONFLUENCE_URL"]
        email = os.environ["CONFLUENCE_EMAIL"]
        token = os.environ["CONFLUENCE_TOKEN"]
        _session = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
    return _session


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _get_page(page_id: str) -> dict | None:
    """Fetch page metadata. Returns None if page doesn't exist."""
    client = _get_session()
    resp = client.get(f"/api/v2/pages/{page_id}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _create_page(title: str, parent_id: str, space_id: str, body_html: str) -> str:
    """Create a child page. Returns new page ID."""
    client = _get_session()
    resp = client.post(
        "/api/v2/pages",
        json={
            "spaceId": space_id,
            "parentId": parent_id,
            "title": title,
            "status": "current",
            "body": {
                "representation": "storage",
                "value": body_html,
            },
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _update_page(page_id: str, title: str, body_html: str, version: int) -> None:
    """Update an existing page (version bump)."""
    client = _get_session()
    resp = client.put(
        f"/api/v2/pages/{page_id}",
        json={
            "id": page_id,
            "title": title,
            "status": "current",
            "version": {"number": version + 1},
            "body": {
                "representation": "storage",
                "value": body_html,
            },
        },
    )
    resp.raise_for_status()
    _set_full_width(page_id)


def _set_full_width(page_id: str) -> None:
    """Set the page appearance to full-width via content properties API.

    Both the "published" (view mode) and "draft" (editor) appearance keys are
    set — Confluence Cloud can otherwise revert to narrow width the next time
    the page is opened in the editor even though the published property alone
    is what live viewers see.
    """
    client = _get_session()
    for prop_key in ("content-appearance-published", "content-appearance-draft"):
        url = f"/rest/api/content/{page_id}/property/{prop_key}"

        resp = client.get(url)
        if resp.status_code == 200:
            existing = resp.json()
            version = existing.get("version", {}).get("number", 0)
            client.put(
                url,
                json={
                    "key": prop_key,
                    "value": {"contentAppearance": "full-width"},
                    "version": {"number": version + 1},
                },
            ).raise_for_status()
        else:
            client.post(
                f"/rest/api/content/{page_id}/property",
                json={
                    "key": prop_key,
                    "value": {"contentAppearance": "full-width"},
                },
            ).raise_for_status()


def publish_page(title: str, body_html: str) -> str:
    """Create or update the pipeline's child page. Returns page ID."""
    parent_id = os.environ["CONFLUENCE_PARENT_PAGE_ID"]
    space = os.environ["CONFLUENCE_SPACE"]

    state = _load_state()
    page_id = state.get("child_page_id")

    if page_id:
        page = _get_page(page_id)
        if page:
            version = page["version"]["number"]
            _update_page(page_id, title, body_html, version)
            return page_id

    # Resolve space ID from space key
    client = _get_session()
    resp = client.get("/api/v2/spaces", params={"keys": space})
    resp.raise_for_status()
    spaces = resp.json().get("results", [])
    if not spaces:
        raise RuntimeError(f"Space '{space}' not found")
    space_id = spaces[0]["id"]

    page_id = _create_page(title, parent_id, space_id, body_html)
    _set_full_width(page_id)
    state["child_page_id"] = page_id
    _save_state(state)
    return page_id


def publish_named_page(title: str, parent_id: str, body_html: str, state_key: str) -> str:
    """Create or update a named page under an arbitrary parent. Returns page ID.

    Idempotent per state_key (tracked in .state.json under "pages") — a distinct
    state_key gets its own page; re-using the same state_key updates that page
    in place rather than creating a duplicate.
    """
    space = os.environ["CONFLUENCE_SPACE"]

    state = _load_state()
    pages = state.setdefault("pages", {})
    page_id = pages.get(state_key)

    if page_id:
        page = _get_page(page_id)
        if page:
            version = page["version"]["number"]
            _update_page(page_id, title, body_html, version)
            return page_id

    client = _get_session()
    resp = client.get("/api/v2/spaces", params={"keys": space})
    resp.raise_for_status()
    spaces = resp.json().get("results", [])
    if not spaces:
        raise RuntimeError(f"Space '{space}' not found")
    space_id = spaces[0]["id"]

    page_id = _create_page(title, parent_id, space_id, body_html)
    _set_full_width(page_id)
    pages[state_key] = page_id
    _save_state(state)
    return page_id


def get_child_pages_with_history(parent_page_id: str) -> list[dict]:
    """Get all child pages of a parent with creation dates.

    Returns list of {id, title, created_date (ISO string), url}.
    """
    client = _get_session()
    results: list[dict] = []
    start = 0
    limit = 100

    while True:
        resp = client.get(
            f"/rest/api/content/{parent_page_id}/child/page",
            params={"expand": "history", "limit": limit, "start": start},
        )
        resp.raise_for_status()
        data = resp.json()
        base = data.get("_links", {}).get("base", os.environ.get("CONFLUENCE_URL", "").rstrip("/"))

        for page in data.get("results", []):
            webui = page.get("_links", {}).get("webui", "")
            results.append({
                "id": page["id"],
                "title": page.get("title", ""),
                "created_date": page.get("history", {}).get("createdDate", ""),
                "url": f"{base}{webui}" if webui else "",
            })

        if len(data.get("results", [])) < limit:
            break
        start += limit

    return results


def find_page_for_issue(
    issue_key: str,
    exclude_page_ids: set[str] | None = None,
    exclude_title_contains: tuple[str, ...] = (),
) -> dict[str, str] | None:
    """CQL-search the pipeline's Confluence space for a page mentioning the given
    Jira issue key. Returns {"url": str, "title": str, "page_id": str}, or None
    if no page is found.

    Pages whose id is in exclude_page_ids are skipped — used to keep the
    pipeline's own generated report pages from "finding" themselves once they
    mention an issue key in their own table. Pages whose title contains any of
    exclude_title_contains (case-insensitive) are also skipped — used to filter
    out rollup/summary pages that mention many issues but don't document any one
    of them specifically.
    """
    space = os.environ["CONFLUENCE_SPACE"]
    exclude_page_ids = exclude_page_ids or set()
    client = _get_session()
    cql = f'space = "{space}" AND type = page AND text ~ "{issue_key}"'
    resp = client.get("/rest/api/search", params={"cql": cql, "limit": 5})
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    base = data.get("_links", {}).get("base", os.environ["CONFLUENCE_URL"].rstrip("/"))

    for result in results:
        content = result.get("content", {})
        page_id = content.get("id")
        if page_id and page_id in exclude_page_ids:
            continue
        webui = result.get("url") or content.get("_links", {}).get("webui", "")
        title = content.get("title") or result.get("title", "")
        if any(s.lower() in title.lower() for s in exclude_title_contains):
            continue
        if webui:
            return {"url": f"{base}{webui}", "title": title, "page_id": page_id or ""}
    return None


def get_page_body_html(page_id: str) -> str:
    """Fetch a Confluence page's storage-format body HTML, or "" if not found."""
    client = _get_session()
    resp = client.get(f"/rest/api/content/{page_id}", params={"expand": "body.storage"})
    if resp.status_code != 200:
        return ""
    return resp.json().get("body", {}).get("storage", {}).get("value", "") or ""


_space_key_cache: str | None = None


def resolve_space_key() -> str:
    """Return the canonical space key (e.g. "VR") for CONFLUENCE_SPACE, which may
    be set to an alias (e.g. "atd")."""
    global _space_key_cache
    if _space_key_cache is None:
        space = os.environ["CONFLUENCE_SPACE"]
        client = _get_session()
        resp = client.get(f"/rest/api/space/{space}")
        resp.raise_for_status()
        _space_key_cache = resp.json()["key"]
    return _space_key_cache


def page_space_key(page_id: str) -> str | None:
    """Return the canonical space key a page belongs to, or None if the page
    can't be found."""
    client = _get_session()
    resp = client.get(f"/rest/api/content/{page_id}", params={"expand": "space"})
    if resp.status_code != 200:
        return None
    return resp.json().get("space", {}).get("key")


def known_report_page_ids() -> set[str]:
    """All page IDs this pipeline has created/tracked in .state.json — the single
    'Computed Metrics MA' page plus every per-quarter report page. Used to keep
    Confluence-page lookups from matching the pipeline's own pages.
    """
    state = _load_state()
    ids = set(state.get("pages", {}).values())
    child_page_id = state.get("child_page_id")
    if child_page_id:
        ids.add(child_page_id)
    return ids


def upload_attachment(page_id: str, filepath: Path) -> None:
    """Upload or update an attachment on the child page.

    Uses v1 REST API because Confluence Cloud v2 API does not support
    attachment uploads.
    """
    client = _get_session()

    # v1 endpoint for attachments
    url = f"/rest/api/content/{page_id}/child/attachment"
    headers = {"X-Atlassian-Token": "nocheck"}

    # Check if attachment already exists
    resp = client.get(url, params={"filename": filepath.name})
    resp.raise_for_status()
    existing = resp.json().get("results", [])

    if existing:
        att_id = existing[0]["id"]
        resp = client.post(
            f"/rest/api/content/{page_id}/child/attachment/{att_id}/data",
            headers=headers,
            files={"file": (filepath.name, filepath.read_bytes(), "image/png")},
        )
    else:
        resp = client.post(
            url,
            headers=headers,
            files={"file": (filepath.name, filepath.read_bytes(), "image/png")},
        )
    resp.raise_for_status()


def close() -> None:
    """Close the HTTP session."""
    global _session
    if _session:
        _session.close()
        _session = None
