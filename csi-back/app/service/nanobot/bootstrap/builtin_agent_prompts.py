"""内置 AGENT 类型提示词种子数据（原 templates/agent/）。"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from app.models.agent.nanobot import NanobotMemoryDocsModel
from app.schemas.constants import NANOBOT_BUILTIN_WORKSPACE_ID, NanobotMemoryDocTypeEnum

logger = logger.bind(name=__name__)

# 这里面的常量提示词会在系统启动时写入到数据库中，作为基础系统提示词

_IDENTITY_CONTENT = """{#
运行时和记忆信息后续集成到AIO沙盒工具中

## Runtime
{{ runtime }}

## Memory
- 长期记忆（MEMORY）由 Dream 自动维护。
- 个性（SOUL）与用户画像（USER）同样由 Dream 负责更新。
- 最近发生的会话摘要会出现在下方 `Recent History` 段落。

{{ platform_policy }}
{% if channel == 'telegram' or channel == 'qq' or channel == 'discord' %}
## Formatting Tips
本对话在即时通讯应用中进行。使用短段落。避免大号标题（#、##）。尽量少用 **加粗**。不要使用表格 — 请用纯文本列表。
{% elif channel == 'whatsapp' or channel == 'sms' %}
## Formatting Tips
本对话在无法渲染 Markdown 的短信平台上进行。请仅使用纯文本。
{% elif channel == 'email' %}
## Formatting Tips
本对话通过电子邮件进行。用清晰的小节组织内容。Markdown 可能无法渲染 — 保持格式简单。
{% elif channel == 'cli' or channel == 'mochat' %}
## Formatting Tips
输出在终端中渲染。避免 Markdown 标题和表格。使用最少格式的纯文本。
{% endif %}

#}

对话中请直接用文字回复。只有要向特定聊天频道发送消息时才使用 `message` 工具。
{# 重要：要向用户发送文件（图片、文档、音频、视频），你必须使用带 `media` 参数的 `message` 工具调用。示例：message(content="这是文件", media=["/path/to/file.png"]) #}
"""

_PLATFORM_POLICY_CONTENT = """{#
后续集成到AIO沙盒工具中
#}

{% if system == 'Windows' %}
## 平台策略（Windows）
- 你正在 Windows 上运行。不要假定存在 GNU 工具（如 `grep`、`sed` 或 `awk`）。
- 在更可靠时，优先使用 Windows 原生命令或文件类工具。
- 若终端输出乱码，请启用 UTF-8 输出后重试。
{% else %}
## 平台策略（POSIX）
- 你正在 POSIX 系统上运行。请优先使用 UTF-8 与标准 shell 工具。
- 当比 shell 命令更简单或更可靠时，请使用文件类工具。
{% endif %}
"""

_SKILLS_SECTION_CONTENT = """# 技能

以下技能可扩展你的能力。要使用某项技能，请按需要加载并遵循其 SKILL.md 的工作流说明。

{{ skills_summary }}
"""

_CONSOLIDATOR_ARCHIVE_CONTENT = """从本对话中提取关键事实。仅输出符合以下类别的条目，其余一律跳过：
- 用户事实：个人信息、偏好、明确表达的观点、习惯
- 决策：已做出的选择、已达成的结论
- 解决方案：经试错发现的可行做法，尤其是多次失败后才成功的非显而易见的方法
- 事件：计划、截止日期、值得注意的发生事项
- 偏好：沟通方式、工具偏好

优先级：用户纠正与偏好 > 解决方案 > 决策 > 事件 > 环境事实。最有价值的记忆是让用户不必重复自己已经说过的话。

跳过：可从源码推导的代码模式、git 历史，或已有记忆中已记录的内容。

以简洁的要点列表输出，每行一条事实。不要前言，不要评述。
若无值得一提的内容，输出：(nothing)
"""

_MAX_ITERATIONS_MESSAGE_CONTENT = (
    "我已达到工具调用迭代的最大次数（{{ max_iterations }}），"
    "任务尚未完成。你可以尝试将任务拆分为更小的步骤。"
)

_SUBAGENT_SYSTEM_CONTENT = """# Subagent

{{ time_ctx }}

你是由主代理派生的 Subagent，用于完成特定任务。
专注于分配给你的任务。你的最终回复将汇报给主 Agent。

## Workspace
{{ workspace }}
{% if skills_summary %}

## Skills

按需要参考 SKILL.md 以使用技能。

{{ skills_summary }}
{% endif %}
"""

_SUBAGENT_ANNOUNCE_CONTENT = """[Subagent '{{ label }}' {{ status_text }}]

Task: {{ task }}

Result:
{{ result }}

请用自然语言向用户作简要概括，篇幅控制在 1～2 句话。不要提及「Subagent」、任务 ID 等技术细节。
"""

_BUILTIN_DESCRIPTIONS: dict[str, str | None] = {
    "identity": "默认主身份与对话规范",
    "_platform_policy": "【系统】平台策略",
    "_skills_section": "【系统】技能段落包装",
    "_consolidator_archive": "【系统】会话归档摘要",
    "_max_iterations_message": "【系统】达到最大迭代次数提示",
    "_subagent_system": "【系统】Subagent 系统提示",
    "_subagent_announce": "【系统】Subagent 结果通告",
}

_BUILTIN_CONTENT_BY_NAME: dict[str, str] = {
    "identity": _IDENTITY_CONTENT,
    "_platform_policy": _PLATFORM_POLICY_CONTENT,
    "_skills_section": _SKILLS_SECTION_CONTENT,
    "_consolidator_archive": _CONSOLIDATOR_ARCHIVE_CONTENT,
    "_max_iterations_message": _MAX_ITERATIONS_MESSAGE_CONTENT,
    "_subagent_system": _SUBAGENT_SYSTEM_CONTENT,
    "_subagent_announce": _SUBAGENT_ANNOUNCE_CONTENT,
}


async def ensure_builtin_agent_prompts() -> int:
    """确保内置 AGENT 文档存在；已存在则跳过。返回本次新建条数。"""
    created = 0
    now = datetime.now()
    ws = NANOBOT_BUILTIN_WORKSPACE_ID
    for name, content in _BUILTIN_CONTENT_BY_NAME.items():
        existing = await NanobotMemoryDocsModel.find_one(
            {
                "workspace_id": ws,
                "type": NanobotMemoryDocTypeEnum.AGENT,
                "name": name,
            }
        )
        if existing is not None:
            continue
        await NanobotMemoryDocsModel(
            workspace_id=ws,
            type=NanobotMemoryDocTypeEnum.AGENT,
            name=name,
            description=_BUILTIN_DESCRIPTIONS.get(name),
            content=content,
            created_at=now,
            updated_at=now,
        ).insert()
        created += 1
        logger.info("已种子 AGENT 内置提示词: name={}", name)
    return created
