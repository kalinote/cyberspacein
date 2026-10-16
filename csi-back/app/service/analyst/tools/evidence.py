"""Agent 证据链全流程工具，写操作沿用 HITL 并保留独立幂等审计记录。"""

import hashlib
import json
from datetime import datetime, timezone

from loguru import logger
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import ApiException, BadRequestException, ForbiddenException
from app.db.mongodb import get_mongodb
from app.schemas.agent.evidence import (
    EvidenceCreateInput,
    EvidenceDeleteInput,
    EvidenceListInput,
    EvidenceReadInput,
    EvidenceResolveInput,
    EvidenceSaveInput,
    EvidenceValidateInput,
)
from app.service import evidence
from app.service.analyst import evidence as access
from app.service.analyst.context import (
    get_current_agent_id,
    get_current_run_id,
    get_current_session_id,
)
from app.service.analyst.hitl import HitlService
from app.service.evidence_graph import apply_operations, create_graph
from app.service.nanobot.agent.tools.base import Tool


async def prepare_edit(data, user) -> tuple:
    """读取修订并预演操作，供校验和保存工具共同使用。"""
    previous = await evidence.get_chain(data.chain_id)
    await access.require_graph_content_access(previous, user)
    if (
        data.expected_revision is not None
        and previous["revision"] != data.expected_revision
    ):
        raise ApiException(
            240409,
            "证据链修订已变化，请重新读取后合并",
            {"current_revision": previous["revision"]},
        )
    graph, ids = apply_operations(previous, data.operations)
    validation = await access.validate_graph(data.chain_id, graph, previous, user)
    return previous, graph, ids, validation


def replay_result(record: dict, args_hash: str) -> dict:
    """同一请求仅返回已有结果；状态不明时绝不重新执行写入。"""
    if record["args_hash"] != args_hash:
        raise BadRequestException("request_id 已用于不同参数，请勿复用请求标识")
    if record.get("result") is not None:
        return {**record["result"], "replayed": True}
    return {
        "ok": False,
        "request_id": record["request_id"],
        "error": {
            "code": "request_in_progress_or_unknown",
            "message": "该请求正在执行或执行结果尚未确认；请读取证据链核对，不要更换 request_id 重复提交相同操作",
        },
    }


class EvidenceTool(Tool):
    """统一严格输入校验和任务发起人权限，不替换现有 Agent 执行框架。"""

    action = "read"
    read_only = True

    @property
    def parameters(self) -> dict:
        """向模型公开完整输入结构，执行时再进行严格校验。"""
        return self.input_model.model_json_schema()

    async def execute(self, **kwargs) -> str:
        """返回可重试判定的结构化结果，避免将内部异常暴露给模型。"""
        try:
            if len(json.dumps(kwargs, ensure_ascii=False).encode("utf-8")) > 1_000_000:
                raise BadRequestException("单次参数不能超过 1 MB，请拆分批次")
            data = self.input_model.model_validate(kwargs)
            user = await access.require_evidence_user(self.action)
            result = await self.run(data, user)
        except ValidationError as exc:
            result = {
                "ok": False,
                "error": {
                    "code": "invalid_input",
                    "message": "输入参数不符合工具要求",
                    "details": exc.errors(include_input=False, include_url=False),
                },
            }
        except ApiException as exc:
            result = {
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.data,
                },
            }
        except ValueError as exc:
            result = {
                "ok": False,
                "error": {"code": "invalid_operation", "message": str(exc)},
            }
        except Exception:
            logger.exception("证据链工具执行异常：{}", self.name)
            result = {
                "ok": False,
                "error": {
                    "code": "execution_unavailable",
                    "message": "证据链操作未能确认完成；写操作请使用相同 request_id 核对结果",
                },
            }
        return json.dumps(result, ensure_ascii=False, default=str, allow_nan=False)


class EvidenceListTool(EvidenceTool):
    name = "evidence_list"
    description = "按关键词、状态、标签分页查找证据链，返回摘要与修订号。标签为同时匹配；不展开图或源实体。"
    input_model = EvidenceListInput

    async def run(self, data, user) -> dict:
        """查询已有证据链以避免重复创建。"""
        return {"ok": True, **await evidence.list_chains(**data.model_dump())}


class EvidenceReadTool(EvidenceTool):
    name = "evidence_read"
    description = "读取证据链定义和最新 revision。scope 可选 summary/graph/nodes/edges；节点和关系分别分页，按 has_more 继续。引用保持指针，展开内容请用 evidence_resolve。"
    input_model = EvidenceReadInput

    async def run(self, data, user) -> dict:
        """返回有界图定义，不递归展开子链。"""
        chain = await evidence.get_chain(data.chain_id)
        await access.require_graph_content_access(chain, user)
        return {
            "ok": True,
            **access.read_graph_page(chain, data.scope, data.page, data.page_size),
        }


class EvidenceResolveTool(EvidenceTool):
    name = "evidence_resolve"
    description = "实时分页展开实体、固定集合、动态版本或子链节点，返回 endpoint_id 供连线使用。node_id 支持子链/内部节点路径。动态版本每次重新检索，不复制数据，不把未来版本自动加入既有关系依据。"
    input_model = EvidenceResolveInput

    async def run(self, data, user) -> dict:
        """解析引用并检查源数据权限。"""
        chain = await evidence.get_chain(data.chain_id)
        await access.require_graph_content_access(chain, user)
        return {
            "ok": True,
            **await access.resolve_graph_node(
                chain, data.node_id, user, data.page, data.page_size
            ),
        }


class EvidenceValidateTool(EvidenceTool):
    name = "evidence_validate"
    description = "只读检查已有证据链或 operations 预演结果，返回 errors、warnings、diff 和父链引用影响。校验结构、循环引用、端点归属和原文摘录，不保证分析判断真实。临时 ID 仅用于预演，保存以 evidence_save 返回的 id_map 为准。"
    input_model = EvidenceValidateInput

    async def run(self, data, user) -> dict:
        """仅预演，不进入审批也不写入图或审计集合。"""
        try:
            previous, _, ids, validation = await prepare_edit(data, user)
        except (ValidationError, ValueError) as exc:
            return {
                "ok": True,
                "valid": False,
                "errors": [{"code": "invalid_operation", "message": str(exc)}],
                "warnings": [],
                "diff": None,
            }
        return {
            "ok": True,
            "chain_id": data.chain_id,
            "revision": previous["revision"],
            "preview_id_map": ids,
            **validation,
        }


class EvidenceWriteTool(EvidenceTool):
    """写工具先生成审批预览，批准后重新校验，再领取唯一请求并落库。"""

    read_only = False
    exclusive = True

    async def run(self, data, user) -> dict:
        """持久化写入与幂等记录，未知结果不会自动重放。

        请求记录只使用新增集合。记录先于业务写入落库；进程在写入后中断时，
        相同请求会提示核对而不是再次修改图，避免依赖跨集合事务或共享库迁移。
        """
        agent_id, session_id = get_current_agent_id(), get_current_session_id()
        if not agent_id or not session_id:
            raise ForbiddenException("证据链写操作需要有效的 Agent 和会话上下文")
        values = data.model_dump(mode="json")
        args_hash = hashlib.sha256(
            json.dumps([self.name, values], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        key = hashlib.sha256(
            json.dumps(
                [str(user.id), agent_id, data.request_id], ensure_ascii=False
            ).encode()
        ).hexdigest()
        records = get_mongodb()["evidence_agent_requests"]
        existing = await records.find_one({"_id": key})
        if existing:
            return replay_result(existing, args_hash)
        previous, graph, ids, validation = await self.prepare(data, user)
        if not validation["valid"]:
            return {
                "ok": False,
                "error": {"code": "invalid_graph", "message": "候选图未通过校验"},
                "validation": validation,
            }
        payload = {
            "action": self.action,
            "chain_id": getattr(data, "chain_id", None),
            "title": graph.title if graph is not None else previous["title"],
            "expected_revision": getattr(data, "expected_revision", None),
            "request_id": data.request_id,
            "reason": data.reason,
            "diff": validation.get("diff"),
            "warnings": validation.get("warnings", []),
            "affected_references": validation.get("affected_references"),
        }
        outcome = await HitlService.request_approval(
            agent_id, session_id, f"tool:{self.name}", payload
        )
        approved = bool(outcome.approved) and not outcome.rejections
        if approved:
            user = await access.require_evidence_user(self.action)
            if graph is not None:
                validation = await access.validate_graph(
                    getattr(data, "chain_id", "__new__"), graph, previous, user
                )
                if not validation["valid"]:
                    return {
                        "ok": False,
                        "error": {
                            "code": "validation_changed",
                            "message": "审批期间引用发生变化，请重新检查",
                        },
                        "validation": validation,
                    }
            elif previous:
                await access.require_graph_content_access(previous, user)
        rejected = {
            "ok": False,
            "request_id": data.request_id,
            "error": {
                "code": "approval_rejected",
                "message": "操作未获批准",
                "reasons": outcome.rejections,
            },
        }
        record = {
            "_id": key,
            "request_id": data.request_id,
            "args_hash": args_hash,
            "tool": self.name,
            "initiator_user_id": str(user.id),
            "agent_id": agent_id,
            "session_id": session_id,
            "run_id": get_current_run_id(),
            "approval_request_id": outcome.approval_request_id,
            "approval_resolution": outcome.resolution,
            "arguments": values,
            "preview": payload,
            "status": "executing" if approved else "rejected",
            "result": None if approved else rejected,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await records.insert_one(record)
        except DuplicateKeyError:
            return replay_result(await records.find_one({"_id": key}), args_hash)
        if not approved:
            return rejected
        try:
            if self.action == "delete":
                await evidence.delete_chain(data.chain_id, data.expected_revision)
                result = {
                    "ok": True,
                    "chain_id": data.chain_id,
                    "revision": data.expected_revision + 1,
                    "deleted": True,
                }
            else:
                chain = await evidence.write_chain(
                    graph,
                    f"agent:{agent_id}/user:{user.id}",
                    chain_id=getattr(data, "chain_id", None),
                    expected_revision=getattr(data, "expected_revision", None),
                )
                result = {
                    "ok": True,
                    "chain_id": chain["id"],
                    "revision": chain["revision"],
                    "id_map": ids,
                    "summary": evidence.chain_summary(chain),
                    "warnings": validation["warnings"],
                    "changes": {
                        kind: {
                            action: len(items)
                            for action, items in validation["diff"][kind].items()
                        }
                        for kind in ("nodes", "edges")
                    },
                }
            result["request_id"] = data.request_id
        except ApiException as exc:
            result = {
                "ok": False,
                "request_id": data.request_id,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.data,
                },
            }
        # 非业务异常保留 executing，不能断言 MongoDB 写入未发生。
        await records.update_one(
            {"_id": key},
            {
                "$set": {
                    "status": "succeeded" if result["ok"] else "failed",
                    "result": result,
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )
        return result


class EvidenceCreateTool(EvidenceWriteTool):
    name = "evidence_create"
    action = "create"
    description = "经既有审批策略创建并保存证据链草稿；支持 blank/proof/expansion/trace 模板。返回 chain_id、revision 和模板节点/关系 id_map。提供 reason 与唯一 request_id，重试必须保持请求不变。"
    input_model = EvidenceCreateInput

    async def prepare(self, data, user) -> tuple:
        """生成完整模板供审批，不提前创建空链。"""
        graph = create_graph(data)
        ids = {f"node_{index + 1}": node.id for index, node in enumerate(graph.nodes)}
        ids.update(
            {f"edge_{index + 1}": edge.id for index, edge in enumerate(graph.edges)}
        )
        return (
            None,
            graph,
            ids,
            await access.validate_graph("__new__", graph, None, user),
        )


class EvidenceSaveTool(EvidenceWriteTool):
    name = "evidence_save"
    action = "update"
    description = (
        "经既有审批策略原子保存 operations 整批编辑，必须提供最新 expected_revision、reason、request_id。"
        "操作支持 set_metadata(metadata)、add_node(client_key,node)、update_node(node_id,patch)、remove_node(node_id,edge_policy)、"
        "reference_subchain(client_key,chain_id,label,position)、remove_subchain_reference(node_id,edge_policy)、"
        "add_edge(client_key,edge)、update_edge(edge_id,edge_patch)、remove_edge(edge_id)、"
        "update_collection_members(node_id,members,member_mode,edge_policy)、move_nodes(positions)、auto_layout(layout,node_ids,locked_node_ids)。"
        "同批新增对象用 $client_key 引用，如 edge.source='$clue'。子链只保存指针；修改子链内部必须对其 chain_id 单独保存。"
        "删除引用不删除原始实体或子链；有连线时默认拒绝删除，可明确设置 remove_connected。动态版本只保存来源规则。"
        "关系默认 pending，人工确认状态须有用户依据；结构校验不代表事实获证实。"
    )
    input_model = EvidenceSaveInput

    async def prepare(self, data, user) -> tuple:
        """准备可审批的完整批次，错误时不产生部分保存。"""
        return await prepare_edit(data, user)


class EvidenceDeleteTool(EvidenceWriteTool):
    name = "evidence_delete"
    action = "delete"
    description = "经既有审批策略软删除一条证据链，校验 expected_revision；被其他链引用时拒绝。不会删除其子链或任何原始实体。必须提供 reason 和唯一 request_id。"
    input_model = EvidenceDeleteInput

    async def prepare(self, data, user) -> tuple:
        """检查删除目标、修订及父链引用，生成删除影响预览。"""
        chain = await evidence.get_chain(data.chain_id)
        await access.require_graph_content_access(chain, user)
        if chain["revision"] != data.expected_revision:
            raise ApiException(
                240409,
                "证据链修订已变化，请重新读取后决定是否删除",
                {"current_revision": chain["revision"]},
            )
        parents = await access.referencing_chains(data.chain_id)
        errors = (
            [
                {
                    "code": "chain_referenced",
                    "message": "该链仍被其他证据链引用，请先解除引用",
                }
            ]
            if parents["total"]
            else []
        )
        return (
            chain,
            None,
            {},
            {
                "valid": not errors,
                "errors": errors,
                "warnings": [],
                "affected_references": parents,
                "diff": {
                    "deleted": True,
                    "node_count": len(chain["nodes"]),
                    "edge_count": len(chain["edges"]),
                },
            },
        )
