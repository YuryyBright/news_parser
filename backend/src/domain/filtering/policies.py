# domain/filtering/policies.py
from .entities import FilterCriteria


class ColdStartPolicy:
    """Визначає чи потрібна LLM-генерація і коли."""

    def requires_generation(self, criteria: FilterCriteria) -> bool:
        return criteria.is_cold_start()

    def requires_regeneration(self, criteria: FilterCriteria, new_phrases: list[str]) -> bool:
        """Перегенерація потрібна якщо phrases суттєво змінились."""
        if criteria.is_cold_start():
            return True
        old = set(criteria.phrases)
        new = set(new_phrases)
        changed_ratio = len(old.symmetric_difference(new)) / max(len(old), len(new), 1)
        return changed_ratio > 0.5  # > 50% змін → перегенерація


class FeedbackWeightPolicy:
    """Адаптує ваги залежно від кількості feedback-ів."""
    MIN_FEEDBACK_FOR_BOOST = 10

    def adjusted_weights(self, criteria: FilterCriteria):
        from .value_objects import SignalWeights
        if criteria.feedback_count < self.MIN_FEEDBACK_FOR_BOOST:
            return criteria.weights
        # Більше feedback → підвищуємо вагу fb, знижуємо keyword
        return SignalWeights(embedding=0.55, keyword=0.20, feedback=0.25)