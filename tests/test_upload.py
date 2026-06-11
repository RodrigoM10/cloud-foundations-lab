from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from upload_to_object_storage import ensure_bucket, upload


class TestEnsureBucket:
    def test_does_not_create_if_bucket_exists(self):
        s3 = MagicMock()
        ensure_bucket(s3, "my-bucket")
        s3.head_bucket.assert_called_once_with(Bucket="my-bucket")
        s3.create_bucket.assert_not_called()

    def test_creates_bucket_on_client_error(self):
        from botocore.exceptions import ClientError
        s3 = MagicMock()
        s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )

        ensure_bucket(s3, "new-bucket")

        s3.create_bucket.assert_called_once_with(Bucket="new-bucket")


class TestUpload:
    def test_calls_upload_file_with_correct_args(self, tmp_path):
        local_file = tmp_path / "data.json"
        local_file.write_text('{"test": true}')
        s3 = MagicMock()

        upload(s3, local_file, "my-bucket", "processed/data.json")

        s3.upload_file.assert_called_once_with(
            str(local_file), "my-bucket", "processed/data.json"
        )

    def test_upload_uses_string_path(self, tmp_path):
        local_file = tmp_path / "file.csv"
        local_file.write_text("a,b\n1,2")
        s3 = MagicMock()

        upload(s3, local_file, "bucket", "key")

        first_arg = s3.upload_file.call_args[0][0]
        assert isinstance(first_arg, str)


class TestMain:
    def test_main_uploads_processed_files(self, tmp_path):
        processed = tmp_path / "data" / "processed"
        processed.mkdir(parents=True)
        (processed / "push_events.json").write_text("[]")
        (processed / "report.csv").write_text("a,b\n")

        s3 = MagicMock()
        s3.head_bucket.return_value = {}
        s3.list_objects_v2.return_value = {"Contents": []}

        with patch("upload_to_object_storage.boto3.client", return_value=s3), \
             patch("upload_to_object_storage.ROOT", tmp_path):
            from upload_to_object_storage import main
            main()

        uploaded_keys = [
            call_args[0][2] for call_args in s3.upload_file.call_args_list
        ]
        assert any("push_events.json" in k for k in uploaded_keys)
        assert any("report.csv" in k for k in uploaded_keys)

    def test_main_skips_missing_files(self, tmp_path, capsys):
        processed = tmp_path / "data" / "processed"
        processed.mkdir(parents=True)

        s3 = MagicMock()
        s3.head_bucket.return_value = {}
        s3.list_objects_v2.return_value = {"Contents": []}

        with patch("upload_to_object_storage.boto3.client", return_value=s3), \
             patch("upload_to_object_storage.ROOT", tmp_path):
            from upload_to_object_storage import main
            main()

        s3.upload_file.assert_not_called()
