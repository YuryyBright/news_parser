# application/ports.py
"""
Інтерфейси для infrastructure — domain і application не знають про реалізацію.
"""

from abc import ABC, abstractmethod
from typing import Any
import numpy as np

class ITaskQueue(ABC):
    @abstractmethod
    async def enqueue(self, task_name: str, *args: Any, **kwargs: Any) -> str:
        """Повертає task_id."""
        ...
    
    @abstractmethod
    async def get_status(self, task_id: str) -> str:
        """Повертає статус задачі: 'pending', 'in_progress', 'completed', 'failed'."""
        ...

class IEmbeddingService(ABC):
    @abstractmethod
    async def encode(self, texts: list[str]) -> np.ndarray:
        """Повертає матрицю ембеддінгів для списку текстів."""
        ...
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Повертає розмірність ембеддінгів."""
        ...

class ILLMService(ABC):
    @abstractmethod
    async def generate_criteria_phrases(
        self, user_prompt: str, count: int
    ) -> list[str]:
        ...