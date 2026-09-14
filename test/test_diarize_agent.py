from customagents.diarizeagent.diarizeagent import _parse_role_mapping


def test_parse_role_mapping_plain_json():
    raw = '{"doctor_speaker_id": "SPEAKER_00", "patient_speaker_id": "SPEAKER_01", "reasoning": "test"}'
    result = _parse_role_mapping(raw)
    assert result["doctor_speaker_id"] == "SPEAKER_00"
    assert result["patient_speaker_id"] == "SPEAKER_01"


def test_parse_role_mapping_with_markdown_fences():
    raw = '```json\n{"doctor_speaker_id": "SPEAKER_00", "patient_speaker_id": "SPEAKER_01"}\n```'
    result = _parse_role_mapping(raw)
    assert result["doctor_speaker_id"] == "SPEAKER_00"


def test_parse_role_mapping_with_surrounding_text():
    raw = 'Here is the result: {"doctor_speaker_id": "SPEAKER_00", "patient_speaker_id": "SPEAKER_01"} thanks'
    result = _parse_role_mapping(raw)
    assert result["patient_speaker_id"] == "SPEAKER_01"


def test_parse_role_mapping_invalid_returns_none():
    assert _parse_role_mapping("not json at all") is None
    assert _parse_role_mapping("") is None
