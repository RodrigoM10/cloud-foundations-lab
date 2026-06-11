import json
import pytest

from process_events import filter_events, main


def test_filter_keeps_only_push_events():
    events = [
        {"type": "PushEvent", "id": "1"},
        {"type": "WatchEvent", "id": "2"},
        {"type": "PushEvent", "id": "3"},
        {"type": "ForkEvent",  "id": "4"},
    ]
    result = filter_events(events)
    assert len(result) == 2
    assert all(e["type"] == "PushEvent" for e in result)


def test_filter_empty_input():
    assert filter_events([]) == []


def test_filter_no_matches_returns_empty():
    events = [{"type": "ForkEvent"}, {"type": "WatchEvent"}]
    assert filter_events(events) == []


def test_filter_all_match():
    events = [{"type": "PushEvent"}, {"type": "PushEvent"}]
    assert len(filter_events(events)) == 2


def test_filter_custom_event_type():
    events = [{"type": "PushEvent"}, {"type": "ForkEvent"}, {"type": "ForkEvent"}]
    result = filter_events(events, event_type="ForkEvent")
    assert len(result) == 2
    assert all(e["type"] == "ForkEvent" for e in result)


def test_filter_missing_type_field():
    events = [{"id": "1"}, {"type": "PushEvent", "id": "2"}]
    result = filter_events(events)
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_main_writes_filtered_json(tmp_path):
    source = tmp_path / "events.jsonl"
    target = tmp_path / "out.json"
    events = [
        {"type": "PushEvent",  "id": "1"},
        {"type": "WatchEvent", "id": "2"},
        {"type": "PushEvent",  "id": "3"},
    ]
    source.write_text("\n".join(json.dumps(e) for e in events))

    main(source=source, target=target)

    result = json.loads(target.read_text())
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "3"


def test_main_creates_output_directory(tmp_path):
    source = tmp_path / "events.jsonl"
    target = tmp_path / "nested" / "dir" / "out.json"
    source.write_text(json.dumps({"type": "PushEvent", "id": "1"}))

    main(source=source, target=target)

    assert target.exists()
