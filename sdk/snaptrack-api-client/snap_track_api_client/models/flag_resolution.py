from enum import StrEnum


class FlagResolution(StrEnum):
    ACTIONED = "actioned"
    DISMISSED = "dismissed"

    def __str__(self) -> str:
        return str(self.value)
