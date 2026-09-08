from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.flag_reason import FlagReason
from ..models.flag_resolution import FlagResolution
from ..models.flag_status import FlagStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.queue_photo import QueuePhoto


T = TypeVar("T", bound="QueueItem")


@_attrs_define
class QueueItem:
    """
    Attributes:
        created_at (datetime.datetime):
        id (int):
        note (None | str):
        photo_id (int):
        reason (FlagReason):
        reporter_id (int):
        resolution (FlagResolution | None):
        resolved_at (datetime.datetime | None):
        resolved_by_id (int | None):
        status (FlagStatus):
        photo (None | QueuePhoto | Unset):
        reporter_email (None | str | Unset):
    """

    created_at: datetime.datetime
    id: int
    note: None | str
    photo_id: int
    reason: FlagReason
    reporter_id: int
    resolution: FlagResolution | None
    resolved_at: datetime.datetime | None
    resolved_by_id: int | None
    status: FlagStatus
    photo: None | QueuePhoto | Unset = UNSET
    reporter_email: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.queue_photo import QueuePhoto  # noqa: PLC0415

        created_at = self.created_at.isoformat()

        id = self.id

        note: None | str
        note = self.note

        photo_id = self.photo_id

        reason = self.reason.value

        reporter_id = self.reporter_id

        resolution: None | str
        if isinstance(self.resolution, FlagResolution):
            resolution = self.resolution.value
        else:
            resolution = self.resolution

        resolved_at: None | str
        if isinstance(self.resolved_at, datetime.datetime):
            resolved_at = self.resolved_at.isoformat()
        else:
            resolved_at = self.resolved_at

        resolved_by_id: int | None
        resolved_by_id = self.resolved_by_id

        status = self.status.value

        photo: dict[str, Any] | None | Unset
        if isinstance(self.photo, Unset):
            photo = UNSET
        elif isinstance(self.photo, QueuePhoto):
            photo = self.photo.to_dict()
        else:
            photo = self.photo

        reporter_email: None | str | Unset
        if isinstance(self.reporter_email, Unset):
            reporter_email = UNSET
        else:
            reporter_email = self.reporter_email

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "id": id,
                "note": note,
                "photo_id": photo_id,
                "reason": reason,
                "reporter_id": reporter_id,
                "resolution": resolution,
                "resolved_at": resolved_at,
                "resolved_by_id": resolved_by_id,
                "status": status,
            }
        )
        if photo is not UNSET:
            field_dict["photo"] = photo
        if reporter_email is not UNSET:
            field_dict["reporter_email"] = reporter_email

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.queue_photo import QueuePhoto  # noqa: PLC0415

        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = d.pop("id")

        def _parse_note(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        note = _parse_note(d.pop("note"))

        photo_id = d.pop("photo_id")

        reason = FlagReason(d.pop("reason"))

        reporter_id = d.pop("reporter_id")

        def _parse_resolution(data: object) -> FlagResolution | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                resolution_type_0 = FlagResolution(data)

                return resolution_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(FlagResolution | None, data)

        resolution = _parse_resolution(d.pop("resolution"))

        def _parse_resolved_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                resolved_at_type_0 = datetime.datetime.fromisoformat(data)

                return resolved_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        resolved_at = _parse_resolved_at(d.pop("resolved_at"))

        def _parse_resolved_by_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        resolved_by_id = _parse_resolved_by_id(d.pop("resolved_by_id"))

        status = FlagStatus(d.pop("status"))

        def _parse_photo(data: object) -> None | QueuePhoto | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                photo_type_0 = QueuePhoto.from_dict(data)

                return photo_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | QueuePhoto | Unset, data)

        photo = _parse_photo(d.pop("photo", UNSET))

        def _parse_reporter_email(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reporter_email = _parse_reporter_email(d.pop("reporter_email", UNSET))

        queue_item = cls(
            created_at=created_at,
            id=id,
            note=note,
            photo_id=photo_id,
            reason=reason,
            reporter_id=reporter_id,
            resolution=resolution,
            resolved_at=resolved_at,
            resolved_by_id=resolved_by_id,
            status=status,
            photo=photo,
            reporter_email=reporter_email,
        )

        queue_item.additional_properties = d
        return queue_item

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
