"""Optimized IDD link traversal — two-search approach."""

from __future__ import annotations

from . import jira_client


def count_with_linked_idds(
    emulation_jql: str,
    idd_label: str = "ATDT_IDD",
    max_results: int = 300,
) -> dict[str, int]:
    """Count emulations that link to at least one IDD.

    Optimized approach (3 API calls instead of N):
    1. Count total emulations
    2. Fetch IDR issue keys with the IDD label (tiny payload)
    3. Fetch emulation issuelinks and intersect
    """
    total = jira_client.count(emulation_jql)
    if total == 0:
        return {"with_idd": 0, "total": 0, "total_idds": 0}

    idd_keys: set[str] = set()
    idd_issues = jira_client.search(
        f'project = IDR AND labels = "{idd_label}"',
        fields=["key"],
        max_results=500,
    )
    for issue in idd_issues:
        idd_keys.add(issue.get("key", ""))

    if not idd_keys:
        return {"with_idd": 0, "total": total, "total_idds": 0}

    emulations = jira_client.search(
        emulation_jql,
        fields=["issuelinks"],
        max_results=max_results,
    )

    with_idd = 0
    matched_idds: set[str] = set()
    for em in emulations:
        links = em.get("fields", {}).get("issuelinks", [])
        for link in links:
            linked = link.get("outwardIssue") or link.get("inwardIssue")
            if linked:
                linked_key = linked.get("key", "")
                if linked_key in idd_keys:
                    matched_idds.add(linked_key)
                    with_idd += 1
                    break

    return {"with_idd": with_idd, "total": total, "total_idds": len(matched_idds)}
