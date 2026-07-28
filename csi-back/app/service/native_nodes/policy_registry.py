from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.schemas.action.execution import ExecutionPlanNode


class ExecutionPolicy(Protocol):
    """节点调度策略协议。"""

    def is_ready(self, node: ExecutionPlanNode, completed_dependencies: int) -> bool:
        ...

    def execution_keys(self, node: ExecutionPlanNode) -> list[str]:
        ...


class DefaultExecutionPolicy:
    """依赖全部完成后执行一次。"""

    def is_ready(self, node: ExecutionPlanNode, completed_dependencies: int) -> bool:
        return completed_dependencies >= node.effective_in_degree

    def execution_keys(self, node: ExecutionPlanNode) -> list[str]:
        return ["default"]


class ExecutionPolicyRegistry:
    """按注册键和契约版本保存调度策略。"""

    def __init__(self):
        self._policies: dict[tuple[str, int], ExecutionPolicy] = {}

    def register(
        self,
        key: str,
        policy: ExecutionPolicy,
        *,
        contract_versions: Iterable[int] = (1,),
    ) -> None:
        for version in contract_versions:
            registry_key = (key, version)
            current = self._policies.get(registry_key)
            if current is not None and current is not policy:
                raise ValueError(f"Execution Policy 重复注册: {key}@{version}")
            self._policies[registry_key] = policy

    def require(self, key: str, contract_version: int) -> ExecutionPolicy:
        policy = self._policies.get((key, contract_version))
        if policy is None:
            raise ValueError(
                f"Execution Policy 未注册或版本不兼容: {key}@{contract_version}"
            )
        return policy


execution_policies = ExecutionPolicyRegistry()
execution_policies.register("default", DefaultExecutionPolicy())
