"""RabbitMQ 业务消息分片协议测试。"""

import hashlib

import pytest

from csi_base_component_sdk.fragmentation import (
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


def test_fragment_settings_use_defaults_when_environment_is_missing(monkeypatch):
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


def test_fragment_settings_allow_optional_environment_overrides(monkeypatch):
    monkeypatch.setenv("CSI_RABBITMQ_FRAGMENT_THRESHOLD_BYTES", "12")
    monkeypatch.setenv("CSI_RABBITMQ_FRAGMENT_BYTES", "8")
    monkeypatch.setenv("CSI_RABBITMQ_MAX_LOGICAL_MESSAGE_BYTES", "64")

    assert FragmentSettings.from_env() == FragmentSettings(12, 8, 64)


def test_encode_and_reassemble_fragmented_message():
    settings = FragmentSettings(12, 8, 64)
    body = "中文消息内容".encode("utf-8") * 3
    fragments = encode_fragments(body, "message-1", settings)
    assembler = FragmentAssembler[str](settings)

    assert len(fragments) > 1
    result = None
    for index, encoded in enumerate(reversed(fragments)):
        parsed = parse_fragment(
            encoded.body,
            FRAGMENT_MESSAGE_TYPE,
            encoded.headers,
            settings,
        )
        assert parsed is not None
        result = assembler.add(parsed, f"tag-{index}")

    assert result is not None
    assert result.body == body
    assert result.message_id == "message-1"
    assert len(result.tokens) == len(fragments)
    assert assembler.has_pending is False


def test_fragment_assembler_accepts_identical_duplicate_fragment():
    settings = FragmentSettings(4, 2, 16)
    fragments = encode_fragments(b"abcdef", "message-1", settings)
    first = parse_fragment(
        fragments[0].body,
        FRAGMENT_MESSAGE_TYPE,
        fragments[0].headers,
        settings,
    )
    second = parse_fragment(
        fragments[1].body,
        FRAGMENT_MESSAGE_TYPE,
        fragments[1].headers,
        settings,
    )
    third = parse_fragment(
        fragments[2].body,
        FRAGMENT_MESSAGE_TYPE,
        fragments[2].headers,
        settings,
    )
    assembler = FragmentAssembler[int](settings)

    assert first is not None and second is not None and third is not None
    assert assembler.add(first, 1) is None
    assert assembler.add(first, 2) is None
    assert assembler.add(second, 3) is None
    result = assembler.add(third, 4)

    assert result is not None
    assert result.tokens == (1, 2, 3, 4)


def test_fragment_parser_rejects_checksum_mismatch():
    settings = FragmentSettings(4, 2, 16)
    fragments = encode_fragments(b"abcdef", "message-1", settings)
    assembler = FragmentAssembler[int](settings)

    for index, encoded in enumerate(fragments):
        headers = dict(encoded.headers)
        headers["x-csi-original-sha256"] = hashlib.sha256(b"other").hexdigest()
        parsed = parse_fragment(
            encoded.body,
            FRAGMENT_MESSAGE_TYPE,
            headers,
            settings,
        )
        assert parsed is not None
        if index < len(fragments) - 1:
            assert assembler.add(parsed, index) is None
        else:
            with pytest.raises(FragmentProtocolError, match="SHA-256"):
                assembler.add(parsed, index)


def test_encode_rejects_message_over_logical_limit():
    with pytest.raises(FragmentProtocolError, match="超过上限"):
        encode_fragments(
            b"12345",
            "message-1",
            FragmentSettings(2, 1, 4),
        )
