import json

import pytest

from customagents.reportagent.clinicalextraction import ClinicalExtractionAgent


@pytest.fixture
def agent(config):
    return ClinicalExtractionAgent(config)


def test_parse_output_with_missing_keys_returns_empty_lists(agent):
    result = agent._parse_output('{"conditions": [{"display": "Fever"}]}')

    assert result["conditions"] == [{"display": "Fever"}]
    assert result["observations"] == []
    assert result["medicationRequests"] == []
    assert result["serviceRequests"] == []


def test_parse_output_with_all_keys(agent):
    payload = {
        "conditions": [{"display": "Fever"}],
        "observations": [{"display": "Temperature"}],
        "medicationRequests": [{"display": "Paracetamol"}],
        "serviceRequests": [{"display": "CBC"}],
    }
    result = agent._parse_output(json.dumps(payload))

    assert result == payload


def test_parse_output_strips_markdown_fences(agent):
    raw = '```json\n{"conditions": []}\n```'
    result = agent._parse_output(raw)

    assert result["conditions"] == []


def test_parse_output_invalid_json_returns_error(agent):
    result = agent._parse_output("not json")

    assert result["error"] == "JSON_PARSING_FAILED"
    assert "raw_output" in result
