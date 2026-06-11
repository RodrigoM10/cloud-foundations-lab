import json
from unittest.mock import MagicMock, patch
import pytest


class TestKafkaProducer:
    def test_sends_one_message_per_event(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        events_file.write_text(
            '{"type":"PushEvent","repo":"org/a","actor":"alice"}\n'
            '{"type":"ForkEvent","repo":"org/b","actor":"bob"}\n'
        )
        mock_producer = MagicMock()
        mock_future = MagicMock()
        mock_future.get.return_value = MagicMock(offset=0)
        mock_producer.send.return_value = mock_future

        with patch("produce_kafka.EVENTS_FILE", events_file), \
             patch("produce_kafka.KafkaProducer", return_value=mock_producer):
            from produce_kafka import main
            main()

        assert mock_producer.send.call_count == 2

    def test_uses_actor_as_key(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        events_file.write_text('{"type":"PushEvent","repo":"org/repo","actor":"alice"}\n')
        mock_producer = MagicMock()
        mock_future = MagicMock()
        mock_future.get.return_value = MagicMock(offset=0)
        mock_producer.send.return_value = mock_future

        with patch("produce_kafka.EVENTS_FILE", events_file), \
             patch("produce_kafka.KafkaProducer", return_value=mock_producer):
            from produce_kafka import main
            main()

        call_kwargs = mock_producer.send.call_args[1]
        assert call_kwargs["key"] == "alice"

    def test_flushes_and_closes_producer(self, tmp_path):
        events_file = tmp_path / "events.jsonl"
        events_file.write_text('{"type":"PushEvent","repo":"r","actor":"a"}\n')
        mock_producer = MagicMock()
        mock_future = MagicMock()
        mock_future.get.return_value = MagicMock(offset=0)
        mock_producer.send.return_value = mock_future

        with patch("produce_kafka.EVENTS_FILE", events_file), \
             patch("produce_kafka.KafkaProducer", return_value=mock_producer):
            from produce_kafka import main
            main()

        mock_producer.flush.assert_called_once()
        mock_producer.close.assert_called_once()

    def test_missing_events_file_exits_gracefully(self, tmp_path, capsys):
        nonexistent = tmp_path / "no_file.jsonl"

        with patch("produce_kafka.EVENTS_FILE", nonexistent):
            from produce_kafka import main
            main()

        out = capsys.readouterr().out
        assert "no encontrado" in out.lower() or nonexistent.name in out


class TestKafkaConsumer:
    def _make_msg(self, offset, event):
        msg = MagicMock()
        msg.offset = offset
        msg.value = event
        return msg

    def test_prints_each_message(self, capsys):
        msgs = [
            self._make_msg(0, {"type": "PushEvent",  "repo": "org/repo", "actor": "alice"}),
            self._make_msg(1, {"type": "ForkEvent",  "repo": "org/repo", "actor": "bob"}),
        ]
        mock_consumer = MagicMock()
        mock_consumer.__iter__.return_value = iter(msgs)

        with patch("consume_kafka.KafkaConsumer", return_value=mock_consumer), \
             patch("consume_kafka.sys.argv", ["consume_kafka.py"]):
            from consume_kafka import main
            main()

        out = capsys.readouterr().out
        assert "PushEvent" in out
        assert "ForkEvent" in out

    def test_from_beginning_uses_earliest_offset(self):
        mock_consumer = MagicMock()
        mock_consumer.__iter__.return_value = iter([])

        with patch("consume_kafka.KafkaConsumer", return_value=mock_consumer) as mock_cls, \
             patch("consume_kafka.sys.argv", ["consume_kafka.py", "--from-beginning"]):
            from consume_kafka import main
            main()

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["auto_offset_reset"] == "earliest"

    def test_default_uses_latest_offset(self):
        mock_consumer = MagicMock()
        mock_consumer.__iter__.return_value = iter([])

        with patch("consume_kafka.KafkaConsumer", return_value=mock_consumer) as mock_cls, \
             patch("consume_kafka.sys.argv", ["consume_kafka.py"]):
            from consume_kafka import main
            main()

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["auto_offset_reset"] == "latest"

    def test_closes_consumer_after_iteration(self):
        mock_consumer = MagicMock()
        mock_consumer.__iter__.return_value = iter([])

        with patch("consume_kafka.KafkaConsumer", return_value=mock_consumer), \
             patch("consume_kafka.sys.argv", ["consume_kafka.py"]):
            from consume_kafka import main
            main()

        mock_consumer.close.assert_called_once()
