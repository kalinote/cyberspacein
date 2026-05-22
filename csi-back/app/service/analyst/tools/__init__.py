"""业务工具包：注入到 AgentLoop 的 ToolRegistry 中，供 LLM 调用。

全部通过 `ContextVar(current_agent_id / current_session_id)` 拉当前运行的 agent/session；
依赖 `AnalystService` 做 SSE 广播与 HITL 决策的同步（避免跨模块循环依赖，import 在方法体内）。

工具清单：
- `get_current_time` ：返回当前时间字符串，无状态。
- `get_entity`       ：按 `(entity_type, entity_uuid)` 去 Elasticsearch 拉实体。
- `modify_entity`    ：经 `HitlService.request_approval` 人工审批；通过后写回 Elasticsearch。
- `notify_user`      ：SSE `notification` 广播一条消息。
- `write_todos`      ：写 `NanobotSessionModel.todos` + SSE `todos`；供 LLM 自行拆解任务。
- `web_search` / `web_fetch` ：联网搜索与页面抓取（运行参数见 `analyst.web_runtime.WEB_RUNTIME`）。

`AnalystService.build_bot` 会按 agent.tools 白名单过滤业务工具；
`submit_task_result` 每次分析固定注册，不在 agent.tools 白名单内。
"""

from app.service.analyst.tools.get_current_time import GetCurrentTimeTool
from app.service.analyst.tools.get_entity import GetEntityTool
from app.service.analyst.tools.modify_entity import ModifyEntityTool
from app.service.analyst.tools.notify_user import NotifyUserTool
from app.service.analyst.tools.registry import BUSINESS_TOOL_CLASSES, build_business_tools
from app.service.analyst.tools.submit_task_result import SubmitTaskResultTool
from app.service.analyst.tools.web_fetch import WebFetchTool
from app.service.analyst.web_runtime import (
    AnalystWebSearchConfig,
    AnalystWebToolsRuntime,
    WEB_RUNTIME,
)
from app.service.analyst.tools.web_search import WebSearchTool
from app.service.analyst.tools.write_todos import WriteTodosTool

__all__ = [
    "AnalystWebSearchConfig",
    "AnalystWebToolsRuntime",
    "WEB_RUNTIME",
    "GetCurrentTimeTool",
    "GetEntityTool",
    "ModifyEntityTool",
    "NotifyUserTool",
    "WriteTodosTool",
    "WebSearchTool",
    "WebFetchTool",
    "SubmitTaskResultTool",
    "BUSINESS_TOOL_CLASSES",
    "build_business_tools",
]
