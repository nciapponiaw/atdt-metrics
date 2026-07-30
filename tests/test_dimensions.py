"""Unit tests for dimension resolution (mocked Jira client)."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metrics_master.dimensions import resolve_dimension


SETTINGS = {
    "quarters": [
        {"label": "ATDT_FY27Q1_CVELIGHT", "name": "FY27 Q1"},
        {"label": "ATDT_FY26Q4_CVELIGHT", "name": "FY26 Q4"},
    ],
    "closure_labels": ["ATDT_Noinfra", "ATDT_Noenv", "ATDT_nopoc", "atdt_notreproduced"],
}


@patch("metrics_master.dimensions.jira_client.count")
def test_by_quarter(mock_count):
    mock_count.return_value = 10
    dim_spec = {"by_quarter": ["ATDT_FY27Q1_CVELIGHT", "ATDT_FY26Q4_CVELIGHT"]}
    result = resolve_dimension(dim_spec, "project = SHLD", SETTINGS)
    assert result == {"FY27 Q1": 10, "FY26 Q4": 10}
    assert mock_count.call_count == 2


@patch("metrics_master.dimensions.jira_client.count")
def test_by_value(mock_count):
    mock_count.return_value = 5
    dim_spec = {"by_value": {"CVE": "labels = ATDT_CVE", "LC": "labels = LightCycles"}}
    result = resolve_dimension(dim_spec, "project = SHLD", SETTINGS)
    assert result == {"CVE": 5, "LC": 5}


@patch("metrics_master.dimensions.jira_client.count")
def test_by_label_prefix(mock_count):
    mock_count.return_value = 3
    dim_spec = {"by_label_prefix": "ATDT_"}
    result = resolve_dimension(dim_spec, "project = SHLD AND status = Closed", SETTINGS)
    assert len(result) == 4
    assert all(v == 3 for v in result.values())


if __name__ == "__main__":
    test_by_quarter()
    test_by_value()
    test_by_label_prefix()
    print("All dimension tests passed.")
