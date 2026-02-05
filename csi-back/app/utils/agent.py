from datetime import datetime
from typing import Any
from jinja2 import Environment, Undefined
from app.models.agent.agent import AgentAnalysisSessionModel

def modify_entity_approval_description(tool_call: Any, state: Any, runtime: Any) -> str:
    """
    修改实体字段申请提示语
    """
    args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
    field = args.get("field", "Unknown Field")
    return f"Agent 尝试修改 {field} 字段，请确认是否继续。"

async def update_session_status(thread_id: str, status: str) -> AgentAnalysisSessionModel | None:
    """
    更新会话状态
    """
    doc = await AgentAnalysisSessionModel.find_one(AgentAnalysisSessionModel.thread_id == thread_id)
    if doc:
        doc.status = status
        doc.updated_at = datetime.now()
        await doc.save()
    return doc

def normalize_todo(t: Any) -> dict:
    if isinstance(t, dict):
        return {"content": t.get("content", ""), "status": t.get("status", "pending")}
    return {"content": getattr(t, "content", ""), "status": getattr(t, "status", "pending")}


def parse_approval_decision(decisions: list[dict]) -> str:
    if not decisions or not isinstance(decisions[0], dict):
        return "unknown"
    first = decisions[0]
    t = first.get("type")
    if t in ("approve", "reject", "edit"):
        return t
    return "unknown"


def get_step_detail(state_update: Any) -> dict:
    """
    从状态更新中获取步骤详情
    """
    out: dict = {}
    if not isinstance(state_update, dict) or "messages" not in state_update:
        return out
    msgs = state_update.get("messages") or []
    if not msgs:
        return out
    last = msgs[-1]
    tool_calls = last.get("tool_calls") if isinstance(last, dict) else getattr(last, "tool_calls", None)
    if tool_calls:
        out["tool_calls"] = [
            {
                "name": tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", ""),
                "args": tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}),
            }
            for tc in tool_calls
        ]
    else:
        content = last.get("content") if isinstance(last, dict) else getattr(last, "content", None)
        if content is not None:
            text = content if isinstance(content, str) else str(content)
            out["result_summary"] = {
                "content_length": len(text),
                # 内容截取150字
                "preview": text[:150] + ("..." if len(text) > 150 else ""),
            }
    return out

class _SilentUndefined(Undefined):
    def __str__(self) -> str:
        return "!字段值缺失!"

def inject_template_fields(template: str, fields: dict[str, Any]) -> str:
    """
    提示词模板字段注入
    """
    env = Environment(undefined=_SilentUndefined)
    ctx = {k: str(v) for k, v in fields.items()}
    return env.from_string(template).render(**ctx)
