import csv
from unittest.mock import MagicMock, patch
import pytest

from load_postgres import ts, load_csv, run_sql


class TestTs:
    def test_empty_string_returns_none(self):
        assert ts("") is None

    def test_none_returns_none(self):
        assert ts(None) is None

    def test_valid_timestamp_passthrough(self):
        assert ts("2024-01-15 10:00:00") == "2024-01-15 10:00:00"

    def test_any_truthy_string_passthrough(self):
        assert ts("2018-01-01") == "2018-01-01"

    def test_whitespace_passthrough(self):
        # whitespace is truthy — callers should strip if needed
        assert ts("  ") == "  "


class TestRunSql:
    def test_executes_file_content(self, tmp_path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text("CREATE TABLE foo (id INT);")
        cur = MagicMock()

        run_sql(cur, sql_file)

        cur.execute.assert_called_once_with("CREATE TABLE foo (id INT);")


class TestLoadCsv:
    def _write_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def test_returns_row_count(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        self._write_csv(csv_file, [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ])
        cur = MagicMock()

        with patch("load_postgres.execute_values"):
            count = load_csv(cur, "users", csv_file)

        assert count == 2

    def test_applies_transform(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        self._write_csv(csv_file, [{"raw_id": "abc", "raw_name": "Alice"}])
        cur = MagicMock()
        captured = []

        def fake_execute_values(cur, sql, values):
            captured.extend(values)

        transform = lambda r: {"id": r["raw_id"], "name": r["raw_name"]}

        with patch("load_postgres.execute_values", side_effect=fake_execute_values):
            load_csv(cur, "users", csv_file, transform=transform)

        assert captured == [["abc", "Alice"]]

    def test_empty_string_becomes_none(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        self._write_csv(csv_file, [{"id": "1", "optional": ""}])
        cur = MagicMock()
        captured = []

        def fake_execute_values(cur, sql, values):
            captured.extend(values)

        with patch("load_postgres.execute_values", side_effect=fake_execute_values):
            load_csv(cur, "items", csv_file)

        assert captured[0][1] is None

    def test_empty_file_returns_zero(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("id,name\n")
        cur = MagicMock()

        count = load_csv(cur, "users", csv_file)

        assert count == 0

    def test_insert_uses_on_conflict_do_nothing(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        self._write_csv(csv_file, [{"id": "1"}])
        cur = MagicMock()
        captured_sql = []

        def fake_execute_values(cur, sql, values):
            captured_sql.append(sql)

        with patch("load_postgres.execute_values", side_effect=fake_execute_values):
            load_csv(cur, "users", csv_file)

        assert "ON CONFLICT DO NOTHING" in captured_sql[0]
