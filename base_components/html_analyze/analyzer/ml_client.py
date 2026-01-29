import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_PATH = "/api/v1/html-analyze"


def _get_base_url() -> str | None:
    url = os.getenv("ML_SERVICE_BASE_URL")
    if not url or not isinstance(url, str):
        logger.warning("未配置 ML_SERVICE_BASE_URL")
        return None
    return url.rstrip("/")


def _post_batch(path: str, datas: list[dict]) -> list[dict] | None:
    base_url = _get_base_url()
    if not base_url:
        return None
    url = f"{base_url}{path}"
    try:
        resp = requests.post(url, json={"datas": datas}, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, dict):
            logger.error(f"ML 接口返回非对象: {type(body)}")
            return None
        code = body.get("code")
        if code != 0:
            logger.error(f"ML 接口返回 code={code}, message={body.get('message', '')}")
            return None
        data = body.get("data")
        if not isinstance(data, list):
            logger.error(f"ML 接口 data 非列表: {type(data)}")
            return None
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"ML 接口请求失败 {path}: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"ML 接口响应解析失败 {path}: {e}")
        return None


def extract_text_batch(datas: list[dict]) -> list[dict]:
    result = _post_batch(f"{_BASE_PATH}/extract-text-batch", datas)
    return result if result is not None else []


def clean_batch(datas: list[dict]) -> list[dict]:
    result = _post_batch(f"{_BASE_PATH}/clean-batch", datas)
    return result if result is not None else []


def extract_links_batch(datas: list[dict]) -> list[dict]:
    result = _post_batch(f"{_BASE_PATH}/extract-links-batch", datas)
    return result if result is not None else []
