# domain/filtering/entities.py
from dataclasses import dataclass, field
from uuid import UUID
import numpy as np


@dataclass
class FilterCriteria:
    """
    Aggregate root — містить всю конфігурацію фільтрації.
    
    Cold start: phrase_embeddings генеруються через LLM з user_prompt.
    Warm start: оновлюються на основі feedback.
    """
    id: UUID
    user_profile_id: UUID
    phrases: list[str]                          
    phrase_embeddings: np.ndarray | None       
    keywords: list[str]                        
    threshold: float = 0.40
    feedback_prior: float = 0.50              
    language_filter: list[str] = field(default_factory=list) 

    def update_feedback_prior(self, liked: int, disliked: int) -> None:
        """Баєсівський апдейт — не перезаписує, а акумулює."""
        total = liked + disliked
        if total == 0:
            return
        # Beta distribution prior update
        alpha = 1 + liked
        beta  = 1 + disliked
        self.feedback_prior = round(alpha / (alpha + beta), 3)

    def is_cold_start(self) -> bool:
        return self.phrase_embeddings is None or len(self.phrase_embeddings) == 0