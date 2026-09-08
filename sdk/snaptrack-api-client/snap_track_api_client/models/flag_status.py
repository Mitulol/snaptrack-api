from enum import StrEnum


class FlagStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"

    def __str__(self) -> str:
        return str(self.value)
