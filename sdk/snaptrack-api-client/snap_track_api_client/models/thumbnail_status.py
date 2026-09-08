from enum import StrEnum


class ThumbnailStatus(StrEnum):
    FAILED = "failed"
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"

    def __str__(self) -> str:
        return str(self.value)
