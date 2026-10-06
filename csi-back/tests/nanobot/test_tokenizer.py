"""词表缓存、下载边界及保守 token 估算的回归测试。"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.service.nanobot.utils import helpers, tokenizer


@pytest.fixture
def vocab_env(monkeypatch, tmp_path):
    """隔离词表状态、缓存目录和网络，禁止测试下载真实词表。"""
    content = b"test-vocabulary"
    path = tmp_path / hashlib.sha1(tokenizer._VOCAB_URL.encode()).hexdigest()
    encoder = Mock()
    encoder.encode.return_value = [1, 2, 3]
    load = Mock(return_value=encoder)
    stream = Mock(side_effect=AssertionError("测试禁止真实网络请求"))
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(tokenizer, "_ENCODER", None)
    monkeypatch.setattr(tokenizer, "_RETRY_AT", 0.0)
    monkeypatch.setattr(tokenizer, "_VOCAB_SHA256", hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(tokenizer.tiktoken, "get_encoding", load)
    monkeypatch.setattr(tokenizer.httpx, "stream", stream)
    return SimpleNamespace(path=path, content=content, encoder=encoder, load=load, stream=stream)


def test_valid_cache_initializes_once_without_network(vocab_env):
    """已有有效缓存时，初始化和后续复用都不访问网络。"""
    vocab_env.path.write_bytes(vocab_env.content)
    assert tokenizer.get_token_encoder() is vocab_env.encoder
    assert tokenizer.get_token_encoder() is vocab_env.encoder
    vocab_env.load.assert_called_once_with("cl100k_base")
    vocab_env.stream.assert_not_called()


@pytest.mark.parametrize("existing", [None, b"damaged-cache"])
def test_missing_or_invalid_cache_downloads_and_validates(vocab_env, existing):
    """缺失或损坏的缓存必须先通过校验，再交给编码器使用。"""
    if existing is not None:
        vocab_env.path.write_bytes(existing)
    response = httpx.Response(
        200, content=vocab_env.content, request=httpx.Request("GET", tokenizer._VOCAB_URL),
    )
    vocab_env.stream.side_effect = None
    vocab_env.stream.return_value = nullcontext(response)
    assert tokenizer.get_token_encoder() is vocab_env.encoder
    assert vocab_env.path.read_bytes() == vocab_env.content
    assert list(vocab_env.path.parent.glob("*.tmp")) == []
    vocab_env.stream.assert_called_once_with("GET", tokenizer._VOCAB_URL, timeout=5.0)
    vocab_env.load.assert_called_once()


@pytest.mark.parametrize("failure", ["timeout", "hash", "size", "deadline", "write"])
def test_download_failure_never_uses_implicit_unbounded_loader(
    monkeypatch, vocab_env, failure,
):
    """下载及缓存失败时及时降级，禁止继续调用会自行下载的编码器。"""
    content = b"incorrect-vocabulary" if failure == "hash" else vocab_env.content
    response = httpx.Response(
        200, content=content, request=httpx.Request("GET", tokenizer._VOCAB_URL),
    )
    vocab_env.stream.side_effect = None
    vocab_env.stream.return_value = nullcontext(response)
    if failure == "timeout":
        vocab_env.stream.side_effect = httpx.ReadTimeout("模拟词表下载超时")
    elif failure == "size":
        monkeypatch.setattr(tokenizer, "_MAX_VOCAB_BYTES", 2)
    elif failure == "deadline":
        monkeypatch.setattr(
            tokenizer, "time",
            SimpleNamespace(monotonic=Mock(side_effect=[0, 0, 0, 16, 16, 16])),
        )
    elif failure == "write":
        monkeypatch.setattr(type(vocab_env.path), "replace", Mock(side_effect=OSError("缓存只读")))
    assert tokenizer.get_token_encoder() is None
    vocab_env.load.assert_not_called()
    assert not vocab_env.path.exists()
    assert list(vocab_env.path.parent.glob("*.tmp")) == []


def test_failed_load_has_backoff_and_can_recover(monkeypatch, vocab_env):
    """失败后的多个估算共用退避，冷却结束后允许重新加载。"""
    clock = Mock(return_value=10)
    monkeypatch.setattr(tokenizer, "time", SimpleNamespace(monotonic=clock))
    vocab_env.stream.side_effect = httpx.ReadTimeout("模拟下载超时")
    assert tokenizer.get_token_encoder() is None
    clock.return_value = 69
    assert tokenizer.get_token_encoder() is None
    vocab_env.stream.assert_called_once()
    vocab_env.path.write_bytes(vocab_env.content)
    clock.return_value = 70
    assert tokenizer.get_token_encoder() is vocab_env.encoder
    vocab_env.load.assert_called_once()


def test_disabled_cache_falls_back_without_unbounded_download(monkeypatch, vocab_env):
    """显式禁用磁盘缓存时使用保守估算，不进入隐式下载。"""
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", "")
    assert tokenizer.get_token_encoder() is None
    vocab_env.stream.assert_not_called()
    vocab_env.load.assert_not_called()


def test_concurrent_calls_share_one_initialization(vocab_env):
    """并发任务只能初始化一次编码器，避免重复下载或部分缓存。"""
    vocab_env.path.write_bytes(vocab_env.content)
    started = threading.Event()
    release = threading.Event()

    def load(_name):
        """在初始化期间留出并发调用的窗口。"""
        started.set()
        assert release.wait(timeout=3)
        return vocab_env.encoder

    vocab_env.load.side_effect = load
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(tokenizer.get_token_encoder) for _ in range(4)]
        try:
            assert started.wait(timeout=3)
        finally:
            release.set()
        assert [future.result(timeout=3) for future in futures] == [vocab_env.encoder] * 4
    vocab_env.load.assert_called_once()
    vocab_env.stream.assert_not_called()


def test_failed_tokenizer_keeps_nonzero_conservative_budget(vocab_env):
    """词表不可用时，中文、工具定义和消息开销仍计入上下文预算。"""
    vocab_env.stream.side_effect = httpx.ReadTimeout("模拟下载超时")
    messages = [{"role": "user", "content": "中文 abc"}]
    tools = [{"type": "function", "function": {"name": "只读测试"}}]
    expected = len(("中文 abc\n" + json.dumps(tools, ensure_ascii=False)).encode("utf-8")) + 4
    tokens, source = helpers.estimate_prompt_tokens_chain(SimpleNamespace(), "test", messages, tools)
    assert (tokens, source) == (expected, "utf8_upper_bound")
    assert helpers.estimate_message_tokens(messages[0]) == len("中文 abc".encode("utf-8")) + 4
    vocab_env.stream.assert_called_once()


def test_ready_tokenizer_preserves_normal_counts(vocab_env):
    """词表就绪后沿用编码器计数，同时把特殊标记当作普通消息内容。"""
    vocab_env.path.write_bytes(vocab_env.content)
    messages = [{"role": "user", "content": "中文 <|endoftext|>"}]
    assert helpers.estimate_prompt_tokens_chain(SimpleNamespace(), "test", messages) == (7, "tiktoken")
    assert helpers.estimate_message_tokens(messages[0]) == 7
    vocab_env.encoder.encode.assert_called_with("中文 <|endoftext|>", disallowed_special=())


def test_provider_counter_still_takes_priority(vocab_env):
    """提供商有自己的计数器时，不初始化本地词表。"""
    provider = SimpleNamespace(estimate_prompt_tokens=Mock(return_value=(123, "provider")))
    assert helpers.estimate_prompt_tokens_chain(provider, "test", []) == (123, "provider")
    vocab_env.stream.assert_not_called()
    vocab_env.load.assert_not_called()
