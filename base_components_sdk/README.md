# CSI 基础组件 SDK

SDK 2.x 提供执行器无关的组件运行入口。Runner 负责初始化、心跳、取消、标准输出捕获、结构化日志、RabbitMQ 生命周期和幂等结果提交，业务组件只实现一个函数：

```python
from csi_base_component_sdk import ComponentContext, ComponentFailure


def run(ctx: ComponentContext) -> dict | None:
    ctx.logger.info("开始处理", batch_size=100)
    value = ctx.get_config("value")
    if value is None:
        raise ComponentFailure("缺少 value 配置")
    print("print 和标准 logging 也会被采集")
    ctx.report_progress(50, "处理中")
    ctx.raise_if_cancelled()
    return {"value": value}
```

SDK 2.2 起可以通过同一上下文上报服务端预注册的通用资源信号：

```python
ctx.report_signal(
    report_id="health-check:resource-1:20260730T120000Z",
    definition_key="component.demo.health",
    definition_version=1,
    resource_id="resource-1",
    resource_name="演示资源",
    value="abnormal",
    metadata={"message": "健康检查失败"},
)
```

`report_id` 必须在同一次业务观测的网络重试中保持不变。默认上报失败只记录诊断且返回 `False`；确实要求信号成功落库的组件可以传入 `required=True`。本地模式只校验并记录报告，不访问告警后端。

组件由以下命令运行：

```text
csi-component run main:run
```

所有官方基础组件均统一暴露 `main:run`，节点定义无需关心组件内部文件结构。

本地调试可传入配置文件：

```text
csi-component run main:run --local-config config.json
```

配置文件结构为：

```json
{
  "meta": {
    "action_id": "local-action",
    "node_instance_id": "local-node",
    "component_run_id": "local-run",
    "component_id": "local-component",
    "attempt": 1
  },
  "config": {},
  "inputs": {},
  "outputs": {}
}
```

远程运行参数由 CSI 后端派发，不应手工构造。当前 Runner 在结束时仍会调用 Crawlab `save_item()`，这是防止 Crawlab 将任务判断为空结果的临时逻辑，所有相关代码均标记为 `TODO(native-scheduler)`。

日志默认通过有界内存队列批量提交。Linux/Crawlab 使用文件描述符捕获，可覆盖 `print`、标准 `logging`、`os.write`、原生扩展以及继承标准输出的子进程；Windows 本地调试使用 `sys.stdout/sys.stderr` Tee 降级实现。业务结果不受日志提交或 Crawlab 临时结果提交失败影响。
