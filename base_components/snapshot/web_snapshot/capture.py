from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright


@dataclass(slots=True)
class PlaywrightCaptureConfig:
    """定义 Playwright 抓取的运行参数。"""
    headless: bool = True
    page_timeout_ms: int = 60_000
    wait_after_load_ms: int = 1_500
    viewport_width: int = 1440
    viewport_height: int = 900
    proxy_server: str | None = None
    extra_http_headers: dict[str, str] | None = None
    max_concurrency: int = 4
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError(f"max_concurrency 必须 >= 1，当前值: {self.max_concurrency}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries 必须 >= 0，当前值: {self.max_retries}")


@dataclass(slots=True)
class CapturePayload:
    """封装一次抓取返回的二进制内容。"""
    screenshot_bytes: bytes
    mhtml_bytes: bytes | None = None


@dataclass(slots=True)
class CaptureResult:
    """单页抓取的汇总结果。"""
    url: str
    payload: CapturePayload
    capture_elapsed_seconds: float = 0.0
    page_duration_seconds: float = 0.0


def _run_async(coro):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(coro)


class PlaywrightSnapshotCapturer:
    """基于 Playwright 执行网页快照抓取。"""
    def __init__(self, config: PlaywrightCaptureConfig | None = None) -> None:
        self.config = config or PlaywrightCaptureConfig()

    def capture(self, url: str) -> CaptureResult:
        """抓取给定 URL 的单页截图与 MHTML。"""
        results = self.capture_many([url])
        if not results:
            raise ValueError("链接不能为空")
        return results[0]

    def capture_many(self, urls: list[str]) -> list[CaptureResult]:
        """一次启动浏览器，并发抓取多个 URL。勿在已运行的事件循环内调用。"""
        normalized = [u.strip() for u in urls if u.strip()]
        if not normalized:
            return []
        return _run_async(self._capture_many_async(normalized))

    async def _capture_many_async(self, urls: list[str]) -> list[CaptureResult]:
        t_session = time.perf_counter()
        results: list[CaptureResult] = []
        sem = asyncio.Semaphore(self.config.max_concurrency)

        async with async_playwright() as p:
            executable_path = p.chromium.executable_path
            normalized_proxy = self._normalize_proxy_server(self.config.proxy_server)
            if not Path(executable_path).exists():
                raise RuntimeError(
                    "Playwright 浏览器未安装。请先运行：python -m playwright install chromium"
                )
            launch_opts: dict[str, Any] = {"headless": self.config.headless}
            if normalized_proxy:
                launch_opts["proxy"] = {"server": normalized_proxy}
            browser = await p.chromium.launch(**launch_opts)
            context = await self._create_context_async(browser)
            try:

                async def capture_url(seed_url: str) -> CaptureResult:
                    async with sem:
                        logger.info(f"正在采集页面: {seed_url}")
                        t_page = time.perf_counter()
                        max_attempts = self.config.max_retries + 1
                        last_error: BaseException | None = None
                        for attempt in range(max_attempts):
                            if attempt > 0:
                                logger.warning(
                                    f"页面 {seed_url} 第 {attempt} 次重试"
                                    f"（共 {self.config.max_retries} 次）"
                                )
                            page = await context.new_page()
                            try:
                                payload = await self._capture_one_page_async(
                                    page, context, seed_url
                                )
                                page_duration = time.perf_counter() - t_page
                                if attempt > 0:
                                    logger.info(
                                        f"页面 {seed_url} 重试成功"
                                        f"（第 {attempt} 次重试后）"
                                    )
                                if payload.mhtml_bytes is None:
                                    logger.warning(
                                        f"页面 {seed_url} 截图成功，MHTML 未生成"
                                    )
                                return CaptureResult(
                                    url=seed_url,
                                    payload=payload,
                                    page_duration_seconds=page_duration,
                                )
                            except Exception as exc:
                                last_error = exc
                                logger.warning(
                                    f"页面 {seed_url} 截图失败"
                                    f"（第 {attempt + 1}/{max_attempts} 次）: {exc}"
                                )
                            finally:
                                await page.close()
                        assert last_error is not None
                        raise last_error

                gathered = await asyncio.gather(
                    *[capture_url(url) for url in urls],
                    return_exceptions=True,
                )
            finally:
                await context.close()
                await browser.close()

        capture_elapsed = time.perf_counter() - t_session
        for item in gathered:
            if isinstance(item, BaseException):
                logger.error(f"页面采集失败: {item}")
                continue
            item.capture_elapsed_seconds = capture_elapsed
            results.append(item)
            logger.info(
                f"页面 {item.url} 采集用时: {item.page_duration_seconds:.2f} 秒"
            )

        logger.info(
            f"批量采集完成: 成功 {len(results)}/{len(urls)}，会话总用时: {capture_elapsed:.2f} 秒"
        )
        return results

    async def _capture_one_page_async(
        self,
        page: Page,
        context: BrowserContext,
        url: str,
    ) -> CapturePayload:
        await page.goto(url, wait_until="load", timeout=self.config.page_timeout_ms)
        await page.wait_for_timeout(self.config.wait_after_load_ms)
        screenshot = await page.screenshot(full_page=True, type="png")
        mhtml_bytes = await self._capture_mhtml_async(page, context, url)
        return CapturePayload(
            screenshot_bytes=screenshot,
            mhtml_bytes=mhtml_bytes,
        )

    async def _capture_mhtml_async(
        self,
        page: Page,
        context: BrowserContext,
        url: str,
    ) -> bytes | None:
        max_attempts = self.config.max_retries + 1
        for attempt in range(max_attempts):
            if attempt > 0:
                logger.warning(
                    f"页面 {url} MHTML 第 {attempt} 次重试"
                    f"（共 {self.config.max_retries} 次）"
                )
                await page.wait_for_timeout(self.config.wait_after_load_ms)
            try:
                cdp_session = await context.new_cdp_session(page)
                snapshot_data = (
                    await cdp_session.send("Page.captureSnapshot", {"format": "mhtml"})
                )["data"]
                if attempt > 0:
                    logger.info(
                        f"页面 {url} MHTML 重试成功（第 {attempt} 次重试后）"
                    )
                return snapshot_data.encode("utf-8")
            except Exception as exc:
                logger.warning(
                    f"页面 {url} MHTML 生成失败"
                    f"（第 {attempt + 1}/{max_attempts} 次）: {exc}"
                )
        return None

    def _context_options(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            }
        }
        if self.config.extra_http_headers:
            opts["extra_http_headers"] = self.config.extra_http_headers
        return opts

    async def _create_context_async(self, browser: Browser) -> BrowserContext:
        return await browser.new_context(**self._context_options())

    @staticmethod
    def _normalize_proxy_server(proxy_server: str | None) -> str | None:
        if not proxy_server:
            return None
        lower = proxy_server.lower()
        if lower.startswith("socks5h://"):
            return "socks5://" + proxy_server[len("socks5h://") :]
        return proxy_server
