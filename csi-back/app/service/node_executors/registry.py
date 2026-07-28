from app.service.node_executors.base import NodeExecutor


class NodeExecutorRegistry:
    """按执行 Driver 保存一级节点执行器。"""

    def __init__(self):
        self._executors: dict[str, NodeExecutor] = {}

    def register(self, driver: str, executor: NodeExecutor) -> None:
        current = self._executors.get(driver)
        if current is not None and current is not executor:
            raise ValueError(f"节点执行器重复注册: {driver}")
        self._executors[driver] = executor

    def require(self, driver: str) -> NodeExecutor:
        executor = self._executors.get(driver)
        if executor is None:
            raise ValueError(f"节点执行器未注册: {driver}")
        return executor


node_executors = NodeExecutorRegistry()
