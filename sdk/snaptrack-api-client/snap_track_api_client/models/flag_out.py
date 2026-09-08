from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.flag_reason import FlagReason
from ..models.flag_resolution import FlagResolution
from ..models.flag_status import FlagStatus

T = TypeVar("T", bound="FlagOut")


@_attrs_define
class FlagOut:
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
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
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

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
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

        flag_out = cls(
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
        )

        flag_out.additional_properties = d
        return flag_out

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
