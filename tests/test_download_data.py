import gzip
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest

import download_data


class TestDownloadGithub:
    def test_downloads_and_decompresses(self, tmp_path):
        raw_dir = tmp_path / "events"
        raw_dir.mkdir()

        # Fake gzip content: 3 JSON lines
        events = [
            {"type": "PushEvent", "id": str(i)} for i in range(3)
        ]
        jsonl_bytes = "\n".join(json.dumps(e) for e in events).encode()
        gz_bytes = gzip.compress(jsonl_bytes)

        def fake_urlretrieve(url, dest):
            Path(dest).write_bytes(gz_bytes)

        with patch("download_data.RAW", tmp_path), \
             patch("download_data.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            download_data.download_github(date="2024-01-15", hour=14)

        out = tmp_path / "events" / "2024-01-15-14.json"
        assert out.exists()
        lines = out.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_gz_file_removed_after_extraction(self, tmp_path):
        raw_dir = tmp_path / "events"
        raw_dir.mkdir()

        gz_bytes = gzip.compress(b'{"type":"PushEvent"}\n')

        def fake_urlretrieve(url, dest):
            Path(dest).write_bytes(gz_bytes)

        with patch("download_data.RAW", tmp_path), \
             patch("download_data.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            download_data.download_github(date="2024-01-15", hour=14)

        gz_file = tmp_path / "events" / "2024-01-15-14.json.gz"
        assert not gz_file.exists()

    def test_correct_url_is_requested(self, tmp_path):
        raw_dir = tmp_path / "events"
        raw_dir.mkdir()
        gz_bytes = gzip.compress(b'{"type":"PushEvent"}\n')

        captured_urls = []

        def fake_urlretrieve(url, dest):
            captured_urls.append(url)
            Path(dest).write_bytes(gz_bytes)

        with patch("download_data.RAW", tmp_path), \
             patch("download_data.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            download_data.download_github(date="2024-02-20", hour=9)

        assert captured_urls[0] == "https://data.gharchive.org/2024-02-20-9.json.gz"


class TestDownloadOlist:
    def test_calls_kaggle_cli(self, tmp_path):
        with patch("download_data.RAW", tmp_path), \
             patch("download_data.subprocess.run") as mock_run:
            download_data.download_olist()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "kaggle" in args
        assert "olistbr/brazilian-ecommerce" in args
        assert "--unzip" in args

    def test_creates_destination_directory(self, tmp_path):
        with patch("download_data.RAW", tmp_path), \
             patch("download_data.subprocess.run"):
            download_data.download_olist()

        assert (tmp_path / "olist").exists()
