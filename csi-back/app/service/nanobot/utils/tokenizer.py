"""有界加载并复用 token 词表，避免运行时隐式无限等待下载。"""

import hashlib
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

import httpx
import tiktoken
from loguru import logger

_VOCAB_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
_VOCAB_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
_DOWNLOAD_TIMEOUT_SECONDS = 15
_RETRY_SECONDS = 60
_MAX_VOCAB_BYTES = 2_000_000
_ENCODER: tiktoken.Encoding | None = None
_RETRY_AT = 0.0
_LOAD_LOCK = threading.Lock()


def get_token_encoder() -> tiktoken.Encoding | None:
    """加载并缓存 cl100k_base；失败后短暂退避，供调用方使用保守估算。

    遵循 tiktoken 的缓存目录、文件名和内容校验规则，先以有超时的请求
    准备词表，再初始化编码器。此函数包含同步 I/O，应在线程中调用。

    Returns:
        已初始化的编码器；下载、校验或缓存不可用时返回 None。
    """
    global _ENCODER, _RETRY_AT
    if _ENCODER is not None:
        return _ENCODER
    with _LOAD_LOCK:
        if _ENCODER is not None:
            return _ENCODER
        if time.monotonic() < _RETRY_AT:
            return None
        started = time.monotonic()
        try:
            cache_dir = os.environ.get(
                "TIKTOKEN_CACHE_DIR",
                os.environ.get(
                    "DATA_GYM_CACHE_DIR",
                    str(Path(tempfile.gettempdir()) / "data-gym-cache"),
                ),
            )
            if not cache_dir:
                raise ValueError("词表缓存目录被禁用，无法保证编码器离线初始化")
            cache_path = Path(cache_dir) / hashlib.sha1(_VOCAB_URL.encode()).hexdigest()
            data = cache_path.read_bytes() if cache_path.is_file() else b""
            if hashlib.sha256(data).hexdigest() != _VOCAB_SHA256:
                logger.info("token 词表缓存缺失或失效，开始限时加载")
                deadline = time.monotonic() + _DOWNLOAD_TIMEOUT_SECONDS
                chunks = []
                size = 0
                with httpx.stream("GET", _VOCAB_URL, timeout=5.0) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= deadline:
                            raise TimeoutError("token 词表下载超过总时限")
                        size += len(chunk)
                        if size > _MAX_VOCAB_BYTES:
                            raise ValueError("token 词表下载超过大小限制")
                        chunks.append(chunk)
                data = b"".join(chunks)
                if hashlib.sha256(data).hexdigest() != _VOCAB_SHA256:
                    raise ValueError("token 词表 SHA256 校验失败")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = cache_path.with_name(f"{cache_path.name}.{uuid.uuid4().hex}.tmp")
                try:
                    temporary.write_bytes(data)
                    temporary.replace(cache_path)
                finally:
                    temporary.unlink(missing_ok=True)

            # 缓存已校验，tiktoken 可直接读取，不再触发其无超时的下载路径。
            _ENCODER = tiktoken.get_encoding("cl100k_base")
            logger.info("token 词表初始化完成，耗时 {:.2f} 秒", time.monotonic() - started)
            return _ENCODER
        except Exception as exc:
            _RETRY_AT = time.monotonic() + _RETRY_SECONDS
            logger.warning(
                "token 词表加载失败，耗时 {:.2f} 秒；使用保守估算，{} 秒后允许重试：{}",
                time.monotonic() - started, _RETRY_SECONDS, exc,
            )
            return None
