"""后端 RabbitMQ 业务消息分片协议测试。"""

import pytest

from app.db.rabbitmq_fragmentation import (
    DEFAULT_FRAGMENT_BYTES,
    DEFAULT_FRAGMENT_THRESHOLD_BYTES,
    DEFAULT_MAX_LOGICAL_MESSAGE_BYTES,
    FRAGMENT_MESSAGE_TYPE,
    FragmentAssembler,
    FragmentProtocolError,
    FragmentSettings,
    encode_fragments,
    parse_fragment,
)


def test_fragment_settings_keep_defaults_without_environment(monkeypatch):
    for key in (
        "CSI_RABBITMQ_FRAGMENT_THRESHOLD_BYTES",
        "CSI_RABBITMQ_FRAGMENT_BYTES",
        "CSI_RABBITMQ_MAX_LOGICAL_MESSAGE_BYTES",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = FragmentSettings.from_env()

    assert settings.threshold_bytes == DEFAULT_FRAGMENT_THRESHOLD_BYTES
    assert settings.fragment_bytes == DEFAULT_FRAGMENT_BYTES
    assert (
        settings.max_logical_message_bytes
        == DEFAULT_MAX_LOGICAL_MESSAGE_BYTES
    )


def test_backend_protocol_reassembles_out_of_order_fragments():
    settings = FragmentSettings(12, 8, 64)
    body = "后端分片消息".encode("utf-8") * 3
    fragments = encode_fragments(body, "message-1", settings)
    assembler = FragmentAssembler[int](settings)

    result = None
    for token, encoded in enumerate(reversed(fragments)):
        fragment = parse_fragment(
            encoded.body,
            FRAGMENT_MESSAGE_TYPE,
            encoded.headers,
            settings,
        )
        assert fragment is not None
        result = assembler.add(fragment, token)

    assert result is not None
    assert result.body == body
    assert result.message_id == "message-1"
    assert len(result.tokens) == len(fragments)


def test_backend_protocol_rejects_invalid_fragment_metadata():
    with pytest.raises(FragmentProtocolError, match="缺少有效元数据"):
        parse_fragment(
            b"fragment",
            FRAGMENT_MESSAGE_TYPE,
            {},
            FragmentSettings(12, 8, 64),
        )
