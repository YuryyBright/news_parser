# src/application/ports/interest_profile_repo.py
import abc
from uuid import UUID
import numpy as np


class IInterestProfileRepository(abc.ABC):
    """
    Порт (інтерфейс) для сховища профілю інтересів.
    
    Зберігає вектори "цікавих" статей та дозволяє отримувати центроїд 
    (середній вектор), з яким будуть порівнюватися нові статті.
    """

    @abc.abstractmethod
    async def add(
        self,
        article_id: UUID,
        vector: np.ndarray,
        score: float,
        tags: list[str],
    ) -> None:
        """
        Зберігає вектор статті у профіль.
        Якщо article_id вже є — оновлює запис.
        
        Args:
            article_id: Унікальний ідентифікатор статті.
            vector: Вектор статті (embedding).
            score: Оцінка статті.
            tags: Список тегів.
        """
        pass

    @abc.abstractmethod
    async def get_centroid(self) -> np.ndarray | None:
        """
        Повертає центроїд (середній вектор) всіх збережених статей.

        Returns:
            np.ndarray: L2-нормований вектор (наприклад, shape (384,) для e5).
            None: Якщо профіль порожній.
        """
        pass

    @abc.abstractmethod
    async def count(self) -> int:
        """
        Повертає поточну кількість статей у профілі.
        """
        pass

    @abc.abstractmethod
    async def contains(self, article_id: UUID) -> bool:
        """
        Перевіряє, чи збережена стаття у профілі.
        """
        pass