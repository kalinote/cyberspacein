from abc import ABC, abstractmethod
from typing import Any


class BaseMLService(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        pass
