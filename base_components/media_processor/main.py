"""媒体资源处理器，入口为 csi-component run main:run。

组件选择：
    按爬虫输出的正文结构选择，不按平台名称或接口响应是否为 JSON 选择。
    raw_content 为 HTML 正文，需要提取纯文本、净化及替换 HTML 内媒体链接时，
    使用原 html_analyze；其中媒体本地化需同时开启 safe_raw_content 和
    media_localization。若有相对链接，配置 base_url_field=url。
    正文已解析为纯文本、媒体位于 JSON 实体或独立数组时，使用 media_processor。
    HTML 和独立媒体并存时，可由两个节点分别处理；本组件归档清单内的资源，
    不替换 raw_content 或 safe_raw_content 中的链接。详细规则见 README.md。

接口：
    data_in(reference) -> data_out(reference)：逐条读取、处理并向全部下游发送。
    dict_in(value) -> dict_out(value)：直接处理一个业务对象；可与队列输入并用。

业务数据：
    media_resources 为完整媒体清单，元素可为 URL 字符串或带 source_url 的对象；
    对象中的 type、role、width、height 等额外元数据会保留。没有该字段时，
    使用 files_urls 字符串数组。显式空清单表示没有媒体，不解析 raw_content。
    输出保留正文和其他业务字段，media_resources 添加 stored_url、storage_key、
    sha256、size、content_type、attempts、status 和 error；status 取值为
    stored / failed / skipped。error 为 null 或 {code, message, retryable}。
    files_urls 仍为字符串数组：成功项使用归档地址，其他项保留源地址。
    media_summary 包含 status(empty/complete/partial/failed)、total 和逐状态计数。

爬虫接入要求：
    每条数据是可 JSON 序列化的业务对象，一条业务记录对应一个对象。
    走本组件的完整内容链路时，爬虫或前置节点应已准备好 clean_content，
    同时保留原始 raw_content 和业务标识；本组件只校验对象及媒体清单格式。
    media_resources 是完整清单，非 null 时优先使用且不与 files_urls 合并；
    [] 明确表示无媒体，即使 files_urls 非空也不会回退。没有两种清单时按无媒体
    透传，因此采集到媒体时必须显式填充，不能仅放在 raw_content 或 cover_image。
    媒体 URL 需为绝对 HTTP/HTTPS 文件直链；视频版本选择、相对地址补全、
    临时签名和完整正文提取由爬虫完成。视频封面应作为单独媒体项提供。
    下载鉴权使用节点级 download_headers / proxy_url，不读取爬虫 Cookie 配置，
    不读取每项自定义 headers。不同鉴权要求应分配到各自配置的处理节点。
    Scrapy Item 需声明实际使用的 files_urls 或 media_resources 字段；
    普通字典输出直接携带相应数组。

运行约定：
    默认 continue 策略允许单项失败，fail 策略要求全部归档成功。
    输入契约、配置或队列传输错误会终止组件，未确认消息由 SDK 退出时回收。
    媒体处理采用软时间预算，阻塞中的请求受连接/读取超时约束。
    EOS、ABORT、组件运行时限与 RabbitMQ 生命周期由 SDK 管理。

配置：
    max_workers=4，max_resources=100，max_retries=1（不含首次请求）；
    download_size_limit=50M，total_size_limit=200M（包括重试时读取的字节）；
    media_timeout_seconds=600，connect_timeout_seconds=10，read_timeout_seconds=15；
    failure_policy=continue，object_prefix=media_resource，download_headers={}。
    proxy_url 可选，为空时使用 DOWNLOAD_PROXY。对象存储使用 COS_* 环境变量，
    本地单条配置见 test_config.json，队列配置见 test_queue_config.json。
"""

from __future__ import annotations

import json
import logging

from dotenv import load_dotenv

from csi_base_component_sdk import (
    ComponentContext,
    ComponentFailure,
    ReferenceStreamTransportError,
)
from processor import MediaProcessor

load_dotenv()
logger = logging.getLogger("media_processor")


def queue_names(port: dict, name: str) -> list[str]:
    """校验 REFERENCE 接口并将单队列或队列列表转换为去重列表。"""
    if not isinstance(port, dict) or port.get("type") != "reference":
        raise ComponentFailure(f"{name} 必须是 reference 类型接口")
    value = port.get("value")
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or any(
        not isinstance(item, str) or not item.strip() for item in values
    ):
        raise ComponentFailure(f"{name} 必须提供队列名称或队列名称数组")
    return list(dict.fromkeys(values))


def run(component: ComponentContext) -> dict:
    """按 SDK 约定处理队列和单条对象输入，返回结果与处理统计。

    Args:
        component: SDK 下发的接口、配置、心跳和消息传输上下文。

    Returns:
        业务数据处理条数、媒体状态计数，以及可选的 dict_out。

    Raises:
        ComponentFailure: 输入、配置或严格模式下的媒体处理失败。
        ReferenceStreamTransportError: 下游发布或消息确认失败。
    """
    inputs = component.inputs
    input_queues = (
        queue_names(inputs["data_in"], "data_in")
        if inputs.get("data_in") is not None
        else []
    )
    has_dict = "dict_in" in inputs and inputs["dict_in"] is not None
    if has_dict and (
        not isinstance(inputs["dict_in"], dict)
        or inputs["dict_in"].get("type") != "value"
    ):
        raise ComponentFailure("dict_in 必须是 value 类型接口")
    if not input_queues and not has_dict:
        raise ComponentFailure("至少需要 data_in 或 dict_in 输入")
    output_queues = (
        queue_names(component.outputs.get("data_out"), "data_out")
        if input_queues
        else []
    )
    if input_queues and not output_queues:
        raise ComponentFailure("队列模式至少需要一个 data_out 下游队列")
    try:
        processor = MediaProcessor(
            {key: component.get_config(key) for key in component.config}
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise ComponentFailure(f"媒体处理配置无效：{exc}") from exc
    rabbitmq = None
    result = {"processed": 0, "media_stored": 0, "media_failed": 0, "media_skipped": 0}

    def heartbeat() -> None:
        """在主线程检查取消并维持 RabbitMQ 连接心跳。"""
        component.raise_if_cancelled()
        if rabbitmq is not None:
            rabbitmq.process_data_events()
        component.raise_if_cancelled()

    try:
        if input_queues:
            rabbitmq = component.rabbitmq
        for queue in input_queues:
            while True:
                heartbeat()
                message = rabbitmq.get_message(queue)
                if message is None:
                    break
                try:
                    data = processor.process(json.loads(message["body"]), heartbeat)
                except (ValueError, TypeError) as exc:
                    raise ComponentFailure(f"媒体输入或处理结果无效：{exc}") from exc
                heartbeat()
                sent = rabbitmq.send_messages_batch(
                    output_queues, data, message_id=message.get("message_id")
                )
                if sent != len(output_queues):
                    raise ReferenceStreamTransportError(
                        "媒体处理结果未成功发送到全部下游，输入消息未确认"
                    )
                if not rabbitmq.ack_message(message["delivery_tag"]):
                    raise ReferenceStreamTransportError(
                        "媒体处理结果已发送，但输入消息确认失败"
                    )
                component.mark_successful_result()
                result["processed"] += 1
                for state in ("stored", "failed", "skipped"):
                    result[f"media_{state}"] += data["media_summary"][state]
        if has_dict:
            try:
                data = processor.process(inputs["dict_in"].get("value"), heartbeat)
            except (ValueError, TypeError) as exc:
                raise ComponentFailure(f"媒体输入或处理结果无效：{exc}") from exc
            result["dict_out"] = data
            result["processed"] += 1
            for state in ("stored", "failed", "skipped"):
                result[f"media_{state}"] += data["media_summary"][state]
            component.mark_successful_result()
        logger.info(
            "媒体处理完成：数据 %s 条，媒体成功 %s 项，失败 %s 项，跳过 %s 项",
            result["processed"],
            result["media_stored"],
            result["media_failed"],
            result["media_skipped"],
        )
        return result
    finally:
        processor.close()
