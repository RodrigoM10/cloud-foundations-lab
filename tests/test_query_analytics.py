import json
import pytest

from query_analytics import run_query


def write_json(path, events):
    path.write_text(json.dumps(events))


def test_run_query_counts_pushes_per_repo(tmp_path):
    json_file = tmp_path / "events.json"
    write_json(json_file, [
        {"type": "PushEvent", "repo": "org/repo-a"},
        {"type": "PushEvent", "repo": "org/repo-a"},
        {"type": "PushEvent", "repo": "org/repo-b"},
    ])

    result = run_query(json_file)

    assert len(result) == 2
    repos = [row[0] for row in result]
    pushes = [row[1] for row in result]
    assert repos[0] == "org/repo-a"
    assert pushes[0] == 2
    assert repos[1] == "org/repo-b"
    assert pushes[1] == 1


def test_run_query_returns_top_10(tmp_path):
    json_file = tmp_path / "events.json"
    events = [{"type": "PushEvent", "repo": f"org/repo-{i}"} for i in range(15)]
    write_json(json_file, events)

    result = run_query(json_file)

    assert len(result) == 10


def test_run_query_sorted_descending(tmp_path):
    json_file = tmp_path / "events.json"
    write_json(json_file, [
        {"type": "PushEvent", "repo": "z/z"},
        {"type": "PushEvent", "repo": "a/a"},
        {"type": "PushEvent", "repo": "a/a"},
        {"type": "PushEvent", "repo": "a/a"},
    ])

    result = run_query(json_file)

    assert result[0][0] == "a/a"
    assert result[0][1] == 3


def test_run_query_empty_file_returns_empty(tmp_path):
    json_file = tmp_path / "empty.json"
    write_json(json_file, [])

    result = run_query(json_file)

    assert result == []
