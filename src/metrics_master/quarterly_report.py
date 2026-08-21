"""Quarterly Metrics Summary report — computed sections for the per-quarter Confluence page."""

from __future__ import annotations

import html as html_lib
import re
from datetime import date
from typing import Any

from . import jira_client, confluence_client
from .calendar import quarter_boundaries

CAUSES_LINK_TYPE = "Problem/Incident"
POC_LABEL = "ATDT_POC"
LIGHT_CYCLES_LABEL = "LightCycles"
CVE_LABEL = "ATDT_CVE"
RESEARCH_PROJECT_LABEL = "ATD_Project"
MAX_ROWS = 300
EXCERPT_MAX_LEN = 600

_TAG_RE = re.compile(r"<[^>]+>")
_PARAGRAPH_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)

QUALIFYING_THREAT_LEVELS = {"CRITICAL", "HIGH", "MEGA"}
_THREAT_LEVEL_RE = re.compile(
    r"Threat\s+Level:?\s*(\w+)",
    re.IGNORECASE,
)
_FILE_EXT_RE = re.compile(
    r"\b([\w][\w.\-]*\.(?:exe|dll|zip|ps1|bat|vbs|js|msi|hta|scr|lnk|jar|cab|iso|img))\b",
    re.IGNORECASE,
)

# Rollup/summary pages mention many tickets but don't document any single
# emulation — never surface these as "the" Confluence page for a row.
EXCLUDE_PAGE_TITLE_SUBSTRINGS = ("quarterly summary", "metrics")


def _find_emulation_page(
    key: str, target_space: str, exclude_page_ids: set[str]
) -> dict[str, str] | None:
    """The Confluence page that documents this specific emulation.

    Prefers Jira's own "Confluence content" backlinks (the same curated data
    Jira's issue view shows) — precise, since it's Jira/Confluence's own link
    tracking rather than a fuzzy text match. Falls back to a CQL text search
    only when Jira has no such link. Either way, rollup/summary pages (this
    pipeline's own pages, and any page whose title reads as a metrics rollup)
    are filtered out.
    """
    for link in jira_client.get_confluence_remote_links(key):
        title_lower = link["title"].lower()
        if any(s in title_lower for s in EXCLUDE_PAGE_TITLE_SUBSTRINGS):
            continue
        page_id = link.get("page_id", "")
        if page_id:
            if page_id in exclude_page_ids:
                continue
            if confluence_client.page_space_key(page_id) != target_space:
                continue
        return {"url": link["url"], "title": link["title"], "page_id": page_id}

    return confluence_client.find_page_for_issue(
        key,
        exclude_page_ids=exclude_page_ids,
        exclude_title_contains=EXCLUDE_PAGE_TITLE_SUBSTRINGS,
    )


def _first_paragraph_text(body_html: str) -> str:
    """Plain-text first non-empty paragraph from a Confluence/Jira HTML body.

    A raw excerpt, not a generated summary: verbatim source text with tags
    stripped and entities unescaped, truncated to roughly one paragraph.
    """
    if not body_html:
        return ""
    candidates = _PARAGRAPH_RE.findall(body_html) or [body_html]
    for raw in candidates:
        text = html_lib.unescape(_TAG_RE.sub(" ", raw))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            if len(text) > EXCERPT_MAX_LEN:
                text = text[:EXCERPT_MAX_LEN].rsplit(" ", 1)[0] + "…"
            return text
    return ""


def _compute_label_section(quarter_label: str, settings: dict, label: str) -> dict[str, Any]:
    """Done Story-type issues for the quarter carrying `label`, with linked IDDs
    (causes relation), Confluence page lookup, and POC impact. Shared by every
    "Work Breakdown by Category" subsection — they differ only in which label
    scopes the query.
    """
    project = settings.get("jira", {}).get("project", "SHLD")
    jql = (
        f'project = {project} AND issuetype = Story '
        f'AND labels = {label} AND labels = "{quarter_label}" '
        f'AND status = Done ORDER BY created ASC'
    )
    issues = jira_client.search(
        jql, fields=["key", "summary", "status", "labels", "issuelinks"], max_results=MAX_ROWS
    )

    # Exclude the pipeline's own generated report pages from the Confluence-page
    # lookup below — a report can otherwise "find" itself once it mentions an
    # issue key in its own table.
    exclude_page_ids = confluence_client.known_report_page_ids()
    target_space = confluence_client.resolve_space_key()

    rows = []
    all_idds: set[str] = set()

    for i, issue in enumerate(issues, start=1):
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "")
        labels = fields.get("labels", [])
        poc_impact = POC_LABEL in labels

        linked_idds: list[dict[str, str]] = []
        for link in fields.get("issuelinks", []):
            if link.get("type", {}).get("name") == CAUSES_LINK_TYPE:
                outward = link.get("outwardIssue")
                if outward:
                    idd_key = outward.get("key", "")
                    if idd_key:
                        idd_summary = outward.get("fields", {}).get("summary", "")
                        linked_idds.append({"key": idd_key, "summary": idd_summary})
                        all_idds.add(idd_key)

        confluence_page = _find_emulation_page(key, target_space, exclude_page_ids)

        rows.append({
            "seq": i,
            "key": key,
            "summary": summary,
            "status": status,
            "confluence_page": confluence_page,
            "poc_impact": poc_impact,
            "linked_idds": linked_idds,
        })

    return {
        "total": len(issues),
        "total_idds": len(all_idds),
        "rows": rows,
    }


def compute_light_cycles_section(quarter_label: str, settings: dict) -> dict[str, Any]:
    """Light Cycles & IDDs subsection: Done Light Cycle stories for the quarter."""
    section = _compute_label_section(quarter_label, settings, LIGHT_CYCLES_LABEL)
    return {
        "total_light_cycles": section["total"],
        "total_idds": section["total_idds"],
        "rows": section["rows"],
    }


def compute_cve_section(quarter_label: str, settings: dict) -> dict[str, Any]:
    """CVEs & IDDs subsection: Done CVE stories for the quarter."""
    section = _compute_label_section(quarter_label, settings, CVE_LABEL)
    return {
        "total_cves": section["total"],
        "total_idds": section["total_idds"],
        "rows": section["rows"],
    }


def compute_research_projects_section(quarter_label: str, settings: dict) -> dict[str, Any]:
    """Research Projects subsection: Stories labeled ATD_Project for the quarter.

    Unlike Light Cycles/CVEs, there's no status filter here — a research
    project's ticket can be in any status. The Summary column is a raw
    excerpt, not a generated summary: the first paragraph of the linked
    Confluence page's body, or the ticket's own description if no page is
    found — verbatim source text, never fabricated or interpreted.
    """
    project = settings.get("jira", {}).get("project", "SHLD")
    jql = (
        f'project = {project} AND issuetype = Story '
        f'AND labels = {RESEARCH_PROJECT_LABEL} AND labels = "{quarter_label}" '
        f'ORDER BY created ASC'
    )
    issues = jira_client.search(jql, fields=["key", "summary", "status"], max_results=MAX_ROWS)

    exclude_page_ids = confluence_client.known_report_page_ids()
    target_space = confluence_client.resolve_space_key()

    rows = []
    for i, issue in enumerate(issues, start=1):
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "")

        confluence_page = _find_emulation_page(key, target_space, exclude_page_ids)

        excerpt = ""
        if confluence_page and confluence_page.get("page_id"):
            excerpt = _first_paragraph_text(
                confluence_client.get_page_body_html(confluence_page["page_id"])
            )
        if not excerpt:
            excerpt = _first_paragraph_text(jira_client.get_rendered_description(key))

        rows.append({
            "seq": i,
            "key": key,
            "summary": summary,
            "status": status,
            "confluence_page": confluence_page,
            "excerpt": excerpt,
        })

    return {
        "total_research_projects": len(issues),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# TIO Tippers — Response Rate
# ---------------------------------------------------------------------------

def _parse_threat_level(body_html: str) -> str:
    """Extract threat level from a TIO Tipper page body.

    Handles both HTML formats: colored-span (older) and plain-text (newer).
    """
    plain = html_lib.unescape(_TAG_RE.sub(" ", body_html))
    plain = re.sub(r"\s+", " ", plain)
    match = _THREAT_LEVEL_RE.search(plain)
    return match.group(1).upper() if match else ""


def _extract_ioc_text(body_html: str) -> str:
    """Extract plain text from the IOC section of a TIO Tipper page."""
    plain = html_lib.unescape(_TAG_RE.sub(" ", body_html))
    plain = re.sub(r"\s+", " ", plain).strip()
    ioc_match = re.search(r"Indicators of Compromise", plain, re.IGNORECASE)
    if not ioc_match:
        return ""
    after = plain[ioc_match.end():]
    end_match = re.search(
        r"(?:Feedback|Data Sources|Recommendations)", after, re.IGNORECASE
    )
    return after[: end_match.start()] if end_match else after


def _extract_samples_info(body_html: str) -> tuple[str, bool]:
    """Extract samples description and availability from a TIO Tipper page.

    Returns (human_description, has_samples_bool).
    """
    ioc_text = _extract_ioc_text(body_html)
    plain_full = html_lib.unescape(_TAG_RE.sub(" ", body_html))
    plain_full = re.sub(r"\s+", " ", plain_full).strip()

    if re.search(r"No IOC", ioc_text or plain_full, re.IGNORECASE):
        return "No IOCs available", False

    search_text = ioc_text if ioc_text else plain_full
    files = sorted(set(_FILE_EXT_RE.findall(search_text)))
    if files:
        return ", ".join(files), True

    if ioc_text and re.search(r"[a-f0-9]{64}", ioc_text):
        return "Sample hashes available (see IOC section)", True

    # IOC section exists but has no file names or hashes — network-only IOCs
    if ioc_text:
        return "Network IOCs only; no endpoint malware samples", False

    # No IOC section at all — characterise by attack type
    if re.search(
        r"cloud.based|identity|credential|SSO|LDAP|OAuth",
        plain_full,
        re.IGNORECASE,
    ):
        return (
            "Identity/cloud-based attack; no endpoint malware binaries identified",
            False,
        )

    if re.search(
        r"social engineering|phishing|impersonat", plain_full, re.IGNORECASE
    ):
        return (
            "Social engineering/phishing; no endpoint malware binaries identified",
            False,
        )

    return "No specific samples identified", False


def _tipper_number(title: str) -> int:
    """Extract the numeric TIO Tipper number from a page title."""
    match = re.search(r"TIO\s+Tipper\s+(\d+)", title, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _find_atdt_coverage(
    tipper_title: str, all_emulations: list[dict],
) -> dict | None:
    """Find an ATDT emulation row that covers the same threat as a TIO Tipper.

    Matches by CVE number first, then by threat-name keywords.
    """
    cves = re.findall(r"CVE-\d{4}-\d+", tipper_title, re.IGNORECASE)
    if cves:
        for emu in all_emulations:
            summary = emu.get("summary", "")
            if any(cve.upper() in summary.upper() for cve in cves):
                return emu

    name_match = re.search(r"TIO\s+Tipper(?:\s+\d+)?:\s*(.+)", tipper_title, re.IGNORECASE)
    if not name_match:
        return None
    threat_name = name_match.group(1).strip()

    generic = {
        "ransomware", "malware", "attack", "campaign", "vulnerability",
        "exploitation", "exploit", "tool", "compromise", "threat", "group",
        "phishing", "supply", "chain", "server", "ongoing", "surge",
        "increase", "uptick", "fake", "updated", "operations", "issued",
        "regarding", "actors", "claims", "breach", "cve", "post",
        "leads", "related", "targeted", "targeting", "attempts",
        "hijacking", "session", "advanced", "cyber", "espionage",
        "reconnaissance", "evasion", "defense", "persistence",
        "exfiltration", "lateral", "movement", "privilege", "escalation",
        "credential", "credentials", "identity", "access", "initial",
        "execution", "discovery", "collection", "techniques", "methods",
        "microsoft", "windows", "active", "directory", "certificate",
        "services", "graph", "calendar", "azure", "cloud", "network",
        "endpoint", "domain", "multiple", "environments", "client",
        "across", "via", "project", "abuse", "novel", "new", "analysis",
        "report", "investigation", "using", "through", "based",
        "impersonation", "delivers", "multi", "stage", "payloads",
        "signed", "evade", "defenses", "deploys",
        "and", "the", "for", "with", "from", "into", "has", "are",
        "was", "not", "but", "use", "uses", "can", "may", "its",
        "all", "over", "data", "theft", "now", "two",
    }
    words = [
        w for w in re.findall(r"\w+", threat_name)
        if w.lower() not in generic and len(w) > 2 and not w.isdigit()
    ]
    if not words:
        return None

    for emu in all_emulations:
        summary_lower = emu.get("summary", "").lower()
        if any(w.lower() in summary_lower for w in words[:3]):
            return emu

    return None


def compute_tio_response_rate_section(
    quarter_label: str,
    settings: dict,
    lc_rows: list[dict],
    cve_rows: list[dict],
) -> dict[str, Any]:
    """TIO Response Rate: qualifying TIO Tippers with ATDT coverage analysis.

    A TIO Tipper qualifies if it was created during the quarter AND its threat
    level is CRITICAL, HIGH, or MEGA.  'Total Thread Events' further restricts
    to those with endpoint samples available for reproduction.
    """
    parent_id = settings.get("confluence", {}).get("tio_tippers_parent_page_id")
    if not parent_id:
        return {
            "total_thread_events": 0,
            "atdt_emulations": 0,
            "response_rate": 0.0,
            "rows": [],
        }

    start_date, end_date = quarter_boundaries(quarter_label)
    all_pages = confluence_client.get_child_pages_with_history(parent_id)

    quarter_pages = []
    for page in all_pages:
        raw = page.get("created_date", "")
        if not raw:
            continue
        try:
            created = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        if start_date <= created <= end_date:
            quarter_pages.append(page)

    quarter_pages.sort(key=lambda p: _tipper_number(p["title"]))
    all_emulations = lc_rows + cve_rows

    rows: list[dict] = []
    total_with_samples = 0
    total_with_coverage = 0

    for page in quarter_pages:
        body_html = confluence_client.get_page_body_html(page["id"])
        threat_level = _parse_threat_level(body_html)

        if threat_level not in QUALIFYING_THREAT_LEVELS:
            continue

        samples_info, has_samples = _extract_samples_info(body_html)
        coverage = _find_atdt_coverage(page["title"], all_emulations)

        if has_samples:
            total_with_samples += 1
            if coverage:
                total_with_coverage += 1

        rows.append({
            "seq": len(rows) + 1,
            "title": page["title"],
            "threat_level": threat_level,
            "url": page["url"],
            "samples_info": samples_info,
            "has_samples": has_samples,
            "coverage": coverage,
        })

    rate = (
        (total_with_coverage / total_with_samples * 100)
        if total_with_samples > 0
        else 0.0
    )

    return {
        "total_thread_events": total_with_samples,
        "atdt_emulations": total_with_coverage,
        "response_rate": round(rate, 1),
        "rows": rows,
    }
