# domain/shared/base_value_object.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """
    Frozen dataclass — порівняння по значенню, не по ідентичності.
    Наслідувати і додавати поля, __eq__ і __hash__ генеруються автоматично.
    """
    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        pass  # override у підкласах