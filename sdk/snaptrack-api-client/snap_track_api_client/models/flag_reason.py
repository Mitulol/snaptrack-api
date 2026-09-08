from enum import StrEnum


class FlagReason(StrEnum):
    COPYRIGHT = "copyright"
    NUDITY = "nudity"
    OTHER = "other"
    SPAM = "spam"
    VIOLENCE = "violence"

    def __str__(self) -> str:
        return str(self.value)
