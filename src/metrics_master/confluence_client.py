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
    state["child_page_id"] = page_id
    _save_state(state)
    return page_id


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
