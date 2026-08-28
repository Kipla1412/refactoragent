import pytest


@pytest.fixture
def search_tool():
    import importlib.util
    from pathlib import Path

    path = Path(".ai-agent/tools/hybridsearch.py")
    spec = importlib.util.spec_from_file_location("hybridsearch_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.MedicalDocumentSearchTool, module.MedicalDocumentSearchParams


def test_build_scope_filter_uses_real_patient_id(search_tool):
    tool_cls, params_cls = search_tool
    params = params_cls(
        query_text="condition",
        vector=[0.1, 0.2],
        patient_id="10008",
    )
    result = tool_cls._build_scope_filter(params)
    assert result == {"term": {"patient_id": "10008"}}


def test_build_scope_filter_rejects_placeholder(search_tool):
    tool_cls, params_cls = search_tool
    params = params_cls(
        query_text="condition",
        vector=[0.1],
        patient_id="patient_id",
        file_id="file_id",
    )
    assert tool_cls._build_scope_filter(params) is None


def test_build_scope_filter_includes_file_id(search_tool):
    tool_cls, params_cls = search_tool
    params = params_cls(
        query_text="condition",
        vector=[0.1],
        patient_id="10008",
        file_id="e024e9c5",
    )
    result = tool_cls._build_scope_filter(params)
    assert result == {
        "bool": {
            "must": [
                {"term": {"patient_id": "10008"}},
                {"term": {"file_id": "e024e9c5"}},
            ]
        }
    }


def test_build_scope_filter_none_when_no_scope(search_tool):
    tool_cls, params_cls = search_tool
    params = params_cls(
        query_text="condition",
        vector=[0.1],
        patient_id="",
    )
    assert tool_cls._build_scope_filter(params) is None
