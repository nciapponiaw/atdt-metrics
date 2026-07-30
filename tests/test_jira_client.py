"""Self-test: validate Jira connectivity and endpoint behavior."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metrics_master import jira_client


def test_count_basic():
    """Smoke test: count issues in SHLD project."""
    result = jira_client.count("project = SHLD")
    assert isinstance(result, int)
    assert result >= 0
    print(f"project = SHLD → {result} issues")


def test_count_done():
    """Count Done emulations."""
    result = jira_client.count(
        "project = SHLD AND (labels = ATDT_CVE OR labels = LightCycles) AND status = Done"
    )
    assert isinstance(result, int)
    print(f"Done emulations → {result}")


if __name__ == "__main__":
    test_count_basic()
    test_count_done()
    print("All Jira client tests passed.")
