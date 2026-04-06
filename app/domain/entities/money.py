from decimal import Decimal, ROUND_HALF_UP, getcontext
from dataclasses import dataclass

getcontext().prec = 28  # precisão 


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "BRL"

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

        normalized = self.amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        object.__setattr__(self, "amount", normalized)

    # -------- Operações -------- #

    def _assert_same_currency(self, other: "Money"):
        if self.currency != other.currency:
            raise ValueError("Cannot operate on different currencies")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, multiplier: int | float | Decimal) -> "Money":
        return Money(self.amount * Decimal(str(multiplier)), self.currency)

    def __truediv__(self, divisor: int | float | Decimal) -> "Money":
        return Money(self.amount / Decimal(str(divisor)), self.currency)

    # -------- Comparações -------- #

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __str__(self):
        return f"{self.currency} {self.amount:.2f}"