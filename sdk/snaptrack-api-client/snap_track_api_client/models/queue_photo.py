from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="QueuePhoto")


@_attrs_define
class QueuePhoto:
    """
    Attributes:
        caption (None | str):
        created_at (datetime.datetime):
        id (int):
        owner_id (int):
    """

    caption: None | str
    created_at: datetime.datetime
    id: int
    owner_id: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        caption: None | str
        caption = self.caption

        created_at = self.created_at.isoformat()

        id = self.id

        owner_id = self.owner_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "caption": caption,
                "created_at": created_at,
                "id": id,
                "owner_id": owner_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_caption(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        caption = _parse_caption(d.pop("caption"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = d.pop("id")

        owner_id = d.pop("owner_id")

        queue_photo = cls(
            caption=caption,
            created_at=created_at,
            id=id,
            owner_id=owner_id,
        )

        queue_photo.additional_properties = d
        return queue_photo

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
