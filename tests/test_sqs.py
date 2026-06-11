import json
from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from produce_sqs import get_or_create_queue
from consume_sqs import get_queue_url


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": ""}}, "op")


class TestGetOrCreateQueue:
    def test_returns_existing_queue_url(self):
        sqs = MagicMock()
        sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs/my-queue"}

        url = get_or_create_queue(sqs, "my-queue")

        assert url == "https://sqs/my-queue"
        sqs.create_queue.assert_not_called()

    def test_creates_queue_when_not_found(self):
        sqs = MagicMock()
        sqs.get_queue_url.side_effect = _client_error(
            "AWS.SimpleQueueService.NonExistentQueue"
        )
        sqs.create_queue.return_value = {"QueueUrl": "https://sqs/new-queue"}

        url = get_or_create_queue(sqs, "new-queue")

        assert url == "https://sqs/new-queue"
        sqs.create_queue.assert_called_once_with(QueueName="new-queue")

    def test_reraises_unexpected_client_error(self):
        sqs = MagicMock()
        sqs.get_queue_url.side_effect = _client_error("AccessDenied")

        with pytest.raises(ClientError):
            get_or_create_queue(sqs, "my-queue")


class TestGetQueueUrl:
    def test_returns_queue_url(self):
        sqs = MagicMock()
        sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs/my-queue"}

        url = get_queue_url(sqs, "my-queue")

        assert url == "https://sqs/my-queue"

    def test_raises_system_exit_when_queue_missing(self):
        sqs = MagicMock()
        sqs.get_queue_url.side_effect = _client_error(
            "AWS.SimpleQueueService.NonExistentQueue"
        )

        with pytest.raises(SystemExit):
            get_queue_url(sqs, "missing-queue")

    def test_reraises_unexpected_error(self):
        sqs = MagicMock()
        sqs.get_queue_url.side_effect = _client_error("AccessDenied")

        with pytest.raises(ClientError):
            get_queue_url(sqs, "my-queue")


class TestProducerMain:
    def test_sends_one_message_per_event(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        events_file.write_text(
            '{"type":"PushEvent","repo":"org/repo","actor":"alice"}\n'
            '{"type":"WatchEvent","repo":"org/repo","actor":"bob"}\n'
        )
        sqs = MagicMock()
        sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs/q"}

        with patch("produce_sqs.EVENTS_FILE", events_file), \
             patch("produce_sqs.boto3.client", return_value=sqs):
            from produce_sqs import main
            main()

        assert sqs.send_message.call_count == 2

    def test_sets_event_type_attribute(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        events_file.write_text('{"type":"PushEvent","repo":"r","actor":"a"}\n')
        sqs = MagicMock()
        sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs/q"}

        with patch("produce_sqs.EVENTS_FILE", events_file), \
             patch("produce_sqs.boto3.client", return_value=sqs):
            from produce_sqs import main
            main()

        call_kwargs = sqs.send_message.call_args[1]
        assert call_kwargs["MessageAttributes"]["event_type"]["StringValue"] == "PushEvent"
