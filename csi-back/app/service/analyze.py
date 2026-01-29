import logging
import re
from datetime import datetime
from typing import Any

from app.db.elasticsearch import get_es
from app.models.analyze.analyze_task import AnalyzeTaskModel
from app.service.ml_client import (
    clean_html,
    detect_language,
    entities_async,
    entities_status,
    extract_text,
    keywords_async,
    keywords_status,
    poll_until_done,
    translate_async,
    translate_status,
)

logger = logging.getLogger(__name__)

CONTENT_ANALYSIS_KEY = "content_analysis"
SUB_STEP_KEYS = [
    "extract_text",
    "clean",
    "language_detect",
    "translate",
    "keywords",
    "entities",
]


def _initial_sub_steps() -> dict:
    return {k: {"status": "pending"} for k in SUB_STEP_KEYS}


async def get_task(entity_type: str, uuid: str) -> AnalyzeTaskModel | None:
    return await AnalyzeTaskModel.find_one(
        AnalyzeTaskModel.entity_type == entity_type,
        AnalyzeTaskModel.uuid == uuid,
    )


def is_content_analysis_running(task: AnalyzeTaskModel | None) -> bool:
    if not task or not task.steps:
        return False
    ca = task.steps.get(CONTENT_ANALYSIS_KEY) or {}
    return ca.get("status") in ("pending", "running")


async def upsert_start_content_analysis(entity_type: str, uuid: str) -> AnalyzeTaskModel:
    task = await get_task(entity_type, uuid)
    now = datetime.utcnow()
    if task:
        task.updated_at = now
        task.steps = task.steps or {}
        task.steps[CONTENT_ANALYSIS_KEY] = {
            "status": "running",
            "sub_steps": _initial_sub_steps(),
        }
        await task.save()
        return task
    task = AnalyzeTaskModel(
        entity_type=entity_type,
        uuid=uuid,
        created_at=now,
        updated_at=now,
        steps={
            CONTENT_ANALYSIS_KEY: {
                "status": "running",
                "sub_steps": _initial_sub_steps(),
            }
        },
    )
    await task.insert()
    return task


async def update_sub_step(
    entity_type: str,
    uuid: str,
    sub_step_key: str,
    status: str,
    ml_status: str | None = None,
    ml_token: str | None = None,
) -> None:
    task = await get_task(entity_type, uuid)
    if not task:
        return
    ca = (task.steps or {}).get(CONTENT_ANALYSIS_KEY) or {}
    sub_steps = ca.get("sub_steps") or {}
    entry = dict(sub_steps.get(sub_step_key) or {})
    entry["status"] = status
    if ml_status is not None:
        entry["ml_status"] = ml_status
    if ml_token is not None:
        entry["ml_token"] = ml_token
    entry.pop("result", None)
    sub_steps[sub_step_key] = entry
    ca["sub_steps"] = sub_steps
    task.steps = task.steps or {}
    task.steps[CONTENT_ANALYSIS_KEY] = ca
    task.updated_at = datetime.utcnow()
    await task.save()


async def set_content_analysis_completed(entity_type: str, uuid: str) -> None:
    task = await get_task(entity_type, uuid)
    if not task:
        return
    ca = (task.steps or {}).get(CONTENT_ANALYSIS_KEY) or {}
    ca["status"] = "completed"
    task.steps = task.steps or {}
    task.steps[CONTENT_ANALYSIS_KEY] = ca
    task.updated_at = datetime.utcnow()
    await task.save()


async def set_content_analysis_failed(
    entity_type: str, uuid: str, error_message: str
) -> None:
    task = await get_task(entity_type, uuid)
    if not task:
        return
    ca = (task.steps or {}).get(CONTENT_ANALYSIS_KEY) or {}
    ca["status"] = "failed"
    ca["error_message"] = error_message
    task.steps = task.steps or {}
    task.steps[CONTENT_ANALYSIS_KEY] = ca
    task.updated_at = datetime.utcnow()
    await task.save()


async def update_entity_doc(entity_type: str, uuid: str, **fields: Any) -> bool:
    es = get_es()
    if not es:
        return False
    index = entity_type if isinstance(entity_type, str) else getattr(entity_type, "value", entity_type)
    if not index or index not in ("article", "forum"):
        return False
    filtered = {k: v for k, v in fields.items() if v is not None}
    if not filtered:
        return True
    try:
        await es.update(index=index, id=uuid, body={"doc": filtered})
        return True
    except Exception as e:
        logger.exception("更新 ES 文档失败 entity_type=%s uuid=%s: %s", entity_type, uuid, e)
        return False


def _empty(s: Any) -> bool:
    if s is None:
        return True
    if isinstance(s, str):
        return not s.strip()
    if isinstance(s, (list, dict)):
        return len(s) == 0
    return False


def _normalize_whitespace(s: str) -> str:
    if not s:
        return s
    s = re.sub(r"[\r\n]+", "\n", s)
    s = re.sub(r" +", " ", s)
    return s


async def _get_es_doc(entity_type: str, uuid: str) -> dict | None:
    es = get_es()
    if not es:
        return None
    index = entity_type if isinstance(entity_type, str) else getattr(entity_type, "value", entity_type)
    try:
        r = await es.get(index=index, id=uuid)
        return (r or {}).get("_source") or {}
    except Exception:
        return None


async def run_content_analysis(entity_type: str, uuid: str) -> None:
    et = entity_type if isinstance(entity_type, str) else getattr(entity_type, "value", entity_type)
    doc = await _get_es_doc(et, uuid)
    if not doc:
        await set_content_analysis_failed(et, uuid, "ES 文档不存在")
        return
    raw_content = doc.get("raw_content") or ""
    if _empty(raw_content):
        await set_content_analysis_failed(et, uuid, "文档缺少 raw_content")
        return

    clean_content = doc.get("clean_content") or ""
    safe_raw_content = doc.get("safe_raw_content") or ""
    language = doc.get("language")
    translation_content = doc.get("translation_content") or ""
    keywords = doc.get("keywords") or []
    entities = doc.get("entities") or {}

    try:
        if _empty(clean_content):
            await update_sub_step(et, uuid, "extract_text", "running")
            try:
                clean_content = await extract_text(raw_content)
                await update_entity_doc(et, uuid, clean_content=clean_content)
                await update_sub_step(et, uuid, "extract_text", "completed")
            except Exception as e:
                logger.exception("extract_text 失败: %s", e)
                await update_sub_step(et, uuid, "extract_text", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "extract_text", "skipped")

        if not _empty(clean_content):
            clean_content = _normalize_whitespace(clean_content)
            await update_entity_doc(et, uuid, clean_content=clean_content)

        if _empty(safe_raw_content):
            await update_sub_step(et, uuid, "clean", "running")
            try:
                safe_raw_content = await clean_html(raw_content)
                await update_entity_doc(et, uuid, safe_raw_content=safe_raw_content)
                await update_sub_step(et, uuid, "clean", "completed")
            except Exception as e:
                logger.exception("clean_html 失败: %s", e)
                await update_sub_step(et, uuid, "clean", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "clean", "skipped")

        if _empty(language) and not _empty(clean_content):
            await update_sub_step(et, uuid, "language_detect", "running")
            try:
                language = await detect_language(clean_content)
                if language is not None:
                    await update_entity_doc(et, uuid, language=language)
                await update_sub_step(et, uuid, "language_detect", "completed")
            except Exception as e:
                logger.exception("detect_language 失败: %s", e)
                await update_sub_step(et, uuid, "language_detect", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "language_detect", "skipped")
        if language is None:
            language = ""

        print(f"翻译文本: {clean_content}")
        if language and language != "ZHO" and _empty(translation_content) and not _empty(clean_content):
            await update_sub_step(et, uuid, "translate", "running", ml_status="pending")
            try:
                token = await translate_async(clean_content, "中文")
                if not token:
                    raise ValueError("翻译接口未返回 token")

                async def fetch():
                    return await translate_status(token)

                async def on_status(s: str):
                    await update_sub_step(et, uuid, "translate", "running", ml_status=s)

                final_status, data = await poll_until_done(fetch, on_status=on_status)
                if final_status == "completed" and data:
                    result_text = data.get("result") or ""
                    await update_entity_doc(et, uuid, translation_content=result_text)
                    await update_sub_step(et, uuid, "translate", "completed", ml_status="completed")
                elif final_status == "failed":
                    err = (data or {}).get("error") or "翻译失败"
                    await update_sub_step(et, uuid, "translate", "failed", ml_status="failed")
                    await set_content_analysis_failed(et, uuid, err)
                    return
                else:
                    await update_sub_step(et, uuid, "translate", "failed", ml_status=final_status)
                    await set_content_analysis_failed(et, uuid, f"翻译超时或异常: {final_status}")
                    return
            except Exception as e:
                logger.exception("translate 失败: %s", e)
                await update_sub_step(et, uuid, "translate", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "translate", "skipped")

        if _empty(keywords) and not _empty(clean_content):
            await update_sub_step(et, uuid, "keywords", "running", ml_status="pending")
            try:
                token = await keywords_async(clean_content)
                if not token:
                    raise ValueError("关键词接口未返回 token")

                async def fetch():
                    return await keywords_status(token)

                async def on_status(s: str):
                    await update_sub_step(et, uuid, "keywords", "running", ml_status=s)

                final_status, data = await poll_until_done(fetch, on_status=on_status)
                if final_status == "completed" and data is not None:
                    kw = data.get("keywords") or []
                    await update_entity_doc(et, uuid, keywords=kw)
                    await update_sub_step(et, uuid, "keywords", "completed", ml_status="completed")
                elif final_status == "failed":
                    err = (data or {}).get("error") or "关键词提取失败"
                    await update_sub_step(et, uuid, "keywords", "failed", ml_status="failed")
                    await set_content_analysis_failed(et, uuid, err)
                    return
                else:
                    await update_sub_step(et, uuid, "keywords", "failed", ml_status=final_status)
                    await set_content_analysis_failed(et, uuid, f"关键词提取超时或异常: {final_status}")
                    return
            except Exception as e:
                logger.exception("keywords 失败: %s", e)
                await update_sub_step(et, uuid, "keywords", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "keywords", "skipped")

        if _empty(entities) and not _empty(clean_content):
            await update_sub_step(et, uuid, "entities", "running", ml_status="pending")
            try:
                token = await entities_async(clean_content)
                if not token:
                    raise ValueError("实体提取接口未返回 token")

                async def fetch():
                    return await entities_status(token)

                async def on_status(s: str):
                    await update_sub_step(et, uuid, "entities", "running", ml_status=s)

                final_status, data = await poll_until_done(fetch, on_status=on_status)
                if final_status == "completed" and data is not None:
                    ent = data.get("entities") or {}
                    await update_entity_doc(et, uuid, entities=ent)
                    await update_sub_step(et, uuid, "entities", "completed", ml_status="completed")
                elif final_status == "failed":
                    err = (data or {}).get("error") or "实体提取失败"
                    await update_sub_step(et, uuid, "entities", "failed", ml_status="failed")
                    await set_content_analysis_failed(et, uuid, err)
                    return
                else:
                    await update_sub_step(et, uuid, "entities", "failed", ml_status=final_status)
                    await set_content_analysis_failed(et, uuid, f"实体提取超时或异常: {final_status}")
                    return
            except Exception as e:
                logger.exception("entities 失败: %s", e)
                await update_sub_step(et, uuid, "entities", "failed")
                await set_content_analysis_failed(et, uuid, str(e))
                return
        else:
            await update_sub_step(et, uuid, "entities", "skipped")

        await set_content_analysis_completed(et, uuid)
    except Exception as e:
        logger.exception("内容分析流水线异常: %s", e)
        await set_content_analysis_failed(et, uuid, str(e))
