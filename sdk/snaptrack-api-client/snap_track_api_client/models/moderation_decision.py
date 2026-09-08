from enum import StrEnum


class ModerationDecision(StrEnum):
    ACTION = "action"
    DISMISS = "dismiss"

    def __str__(self) -> str:
        return str(self.value)
