from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from elasticsearch import ApiError

from app.core.config import settings
from app.db.elasticsearch import get_es
from app.models.action.component_run import ComponentRunModel
from app.schemas.action.log import (
    ActionNodeLogItem,
    ActionNodeLogPage,
    ComponentLogBatchRequest,
    ComponentLogBatchResponse,
)


class ActionLogService:
    @staticmethod
    async def ensure_storage() -> None:
        es = get_es()
        if es is None:
            return
        policy_name = f"{settings.COMPONENT_LOG_DATA_STREAM}-retention"
        template_name = f"{settings.COMPONENT_LOG_DATA_STREAM}-template"
        await es.ilm.put_lifecycle(
            name=policy_name,
            policy={
                "phases": {
                    "hot": {"actions": {}},
                    "delete": {
                        "min_age": f"{settings.COMPONENT_LOG_RETENTION_DAYS}d",
                        "actions": {"delete": {}},
                    },
                }
            },
        )
        await es.indices.put_index_template(
            name=template_name,
            index_patterns=[f"{settings.COMPONENT_LOG_DATA_STREAM}*"],
            data_stream={},
            template={
                "settings": {"index.lifecycle.name": policy_name},
                "mappings": {
                    "dynamic": False,
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "event_id": {"type": "keyword"},
                        "sequence": {"type": "long"},
                        "occurred_at": {"type": "date"},
                        "ingested_at": {"type": "date"},
                        "action_id": {"type": "keyword"},
                        "node_instance_id": {"type": "keyword"},
                        "component_run_id": {"type": "keyword"},
                        "component_id": {"type": "keyword"},
                        "attempt": {"type": "integer"},
                        "level": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "logger": {"type": "keyword"},
                        "message": {"type": "text"},
                        "fields": {"type": "flattened"},
                        "exception": {"type": "text"},
                        "truncated": {"type": "boolean"},
                    },
                },
            },
        )
        try:
            await es.indices.get_data_stream(name=settings.COMPONENT_LOG_DATA_STREAM)
        except ApiError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
            await es.indices.create_data_stream(name=settings.COMPONENT_LOG_DATA_STREAM)

    @staticmethod
    async def ingest(
        component_run: ComponentRunModel,
        batch: ComponentLogBatchRequest,
    ) -> ComponentLogBatchResponse:
        es = get_es()
        if es is None:
            raise RuntimeError("Elasticsearch 未初始化")
        ingested_at = datetime.now(timezone.utc)
        operations: list[dict] = []
        for entry in batch.entries:
            document = entry.model_dump(mode="json")
            document.update(
                {
                    "@timestamp": ingested_at.isoformat(),
                    "ingested_at": ingested_at.isoformat(),
                    "action_id": component_run.action_id,
                    "node_instance_id": component_run.node_instance_id,
                    "component_run_id": component_run.id,
                    "component_id": component_run.component_id,
                    "attempt": component_run.attempt,
                }
            )
            operations.extend(
                [
                    {"create": {"_index": settings.COMPONENT_LOG_DATA_STREAM, "_id": entry.event_id}},
                    document,
                ]
            )
        response = await es.bulk(operations=operations, refresh=False)
        accepted = 0
        duplicated = 0
        failure: str | None = None
        accepted_error_ids: set[str] = set()
        error_ids = {
            entry.event_id for entry in batch.entries if entry.level in {"ERROR", "FATAL"}
        }
        for item in response.get("items", []):
            result = item.get("create", {})
            status = int(result.get("status", 500))
            event_id = str(result.get("_id", ""))
            if status in {200, 201}:
                accepted += 1
                if event_id in error_ids:
                    accepted_error_ids.add(event_id)
            elif status == 409:
                duplicated += 1
            else:
                failure = str(result.get("error") or "Elasticsearch bulk 写入失败")
        await ComponentRunModel.find_one({"_id": component_run.id}).update(
            {
                "$inc": {
                    "log_count": accepted,
                    "error_log_count": len(accepted_error_ids),
                },
                "$max": {"dropped_log_count": batch.dropped_count},
                "$set": {"updated_at": datetime.now()},
            }
        )
        if failure:
            raise RuntimeError(failure)
        return ComponentLogBatchResponse(accepted=accepted, duplicated=duplicated)

    @staticmethod
    def _encode_cursor(sort: list) -> str:
        raw = json.dumps(sort, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> list:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError
            return value
        except Exception as exc:
            raise ValueError("日志 cursor 无效") from exc

    @staticmethod
    async def query(
        node_instance_id: str,
        *,
        cursor: str | None,
        before_cursor: str | None,
        limit: int,
        levels: list[str] | None,
        sources: list[str] | None,
        component_run_id: str | None,
        keyword: str | None,
    ) -> ActionNodeLogPage:
        es = get_es()
        if es is None:
            raise RuntimeError("Elasticsearch 未初始化")
        filters: list[dict] = [{"term": {"node_instance_id": node_instance_id}}]
        if levels:
            filters.append({"terms": {"level": levels}})
        if sources:
            filters.append({"terms": {"source": sources}})
        if component_run_id:
            filters.append({"term": {"component_run_id": component_run_id}})
        must = [{"match": {"message": keyword}}] if keyword else []
        body: dict = {
            "size": limit + 1,
            "query": {"bool": {"filter": filters, "must": must}},
            "sort": [{"ingested_at": "asc"}, {"event_id": "asc"}],
        }
        if cursor and before_cursor:
            raise ValueError("cursor 与 before_cursor 不能同时使用")
        if cursor:
            body["search_after"] = ActionLogService._decode_cursor(cursor)
        elif before_cursor:
            body["search_after"] = ActionLogService._decode_cursor(before_cursor)
            body["sort"] = [{"ingested_at": "desc"}, {"event_id": "desc"}]
        else:
            body["sort"] = [{"ingested_at": "desc"}, {"event_id": "desc"}]
        try:
            response = await es.search(index=settings.COMPONENT_LOG_DATA_STREAM, **body)
        except ApiError as exc:
            if getattr(exc, "status_code", None) == 404:
                return ActionNodeLogPage()
            raise
        hits = response.get("hits", {}).get("hits", [])
        has_more = len(hits) > limit
        hits = hits[:limit]
        if not cursor:
            hits.reverse()
        items = [ActionNodeLogItem.model_validate(hit["_source"]) for hit in hits]
        next_cursor = (
            ActionLogService._encode_cursor(hits[-1]["sort"])
            if hits and not before_cursor
            else cursor
        )
        previous_cursor = (
            ActionLogService._encode_cursor(hits[0]["sort"])
            if hits and has_more and not cursor
            else None
        )
        return ActionNodeLogPage(
            items=items,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
            has_more=has_more,
        )
