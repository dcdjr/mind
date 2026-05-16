from mind.memory_extractor import parse_extracted_memories


def test_parse_extracted_memories_parses_valid_json():
    raw = '["User prefers concise answers."]'

    result = parse_extracted_memories(raw)

    assert result == ["User prefers concise answers."]


def test_parse_extracted_memories_returns_empty_list_for_invalid_json():
    raw = "Sure, here are the memories: User likes Python."

    result = parse_extracted_memories(raw)

    assert result == []


def test_parse_extracted_memories_ignores_non_string_items():
    raw = '["Valid memory.", 123, null, ""]'

    result = parse_extracted_memories(raw)

    assert result == ["Valid memory."]


def test_parse_extracted_memories_handles_extra_text_around_json():
    raw = 'Here are the memories:\n["User wants Mind to stay local-first."]'

    result = parse_extracted_memories(raw)

    assert result == ["User wants Mind to stay local-first."]


def test_parse_extracted_memories_handles_markdown_json_block():
    raw = '```json\n["User wants Mind to stay local-first."]\n```'

    result = parse_extracted_memories(raw)

    assert result == ["User wants Mind to stay local-first."]
