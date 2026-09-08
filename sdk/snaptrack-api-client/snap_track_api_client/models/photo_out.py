from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.thumbnail_out import ThumbnailOut


T = TypeVar("T", bound="PhotoOut")


@_attrs_define
class PhotoOut:
    """
    Attributes:
        content_type (str):
        created_at (datetime.datetime):
        height (int):
        id (int):
        original_filename (str):
        owner_id (int):
        size_bytes (int):
        updated_at (datetime.datetime):
        width (int):
        caption (None | str | Unset):
        thumbnail (None | ThumbnailOut | Unset):
    """

    content_type: str
    created_at: datetime.datetime
    height: int
    id: int
    original_filename: str
    owner_id: int
    size_bytes: int
    updated_at: datetime.datetime
    width: int
    caption: None | str | Unset = UNSET
    thumbnail: None | ThumbnailOut | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.thumbnail_out import ThumbnailOut  # noqa: PLC0415

        content_type = self.content_type

        created_at = self.created_at.isoformat()

        height = self.height

        id = self.id

        original_filename = self.original_filename

        owner_id = self.owner_id

        size_bytes = self.size_bytes

        updated_at = self.updated_at.isoformat()

        width = self.width

        caption: None | str | Unset
        if isinstance(self.caption, Unset):
            caption = UNSET
        else:
            caption = self.caption

        thumbnail: dict[str, Any] | None | Unset
        if isinstance(self.thumbnail, Unset):
            thumbnail = UNSET
        elif isinstance(self.thumbnail, ThumbnailOut):
            thumbnail = self.thumbnail.to_dict()
        else:
            thumbnail = self.thumbnail

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "content_type": content_type,
                "created_at": created_at,
                "height": height,
                "id": id,
                "original_filename": original_filename,
                "owner_id": owner_id,
                "size_bytes": size_bytes,
                "updated_at": updated_at,
                "width": width,
            }
        )
        if caption is not UNSET:
            field_dict["caption"] = caption
        if thumbnail is not UNSET:
            field_dict["thumbnail"] = thumbnail

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.thumbnail_out import ThumbnailOut  # noqa: PLC0415

        d = dict(src_dict)
        content_type = d.pop("content_type")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        height = d.pop("height")

        id = d.pop("id")

        original_filename = d.pop("original_filename")

        owner_id = d.pop("owner_id")

        size_bytes = d.pop("size_bytes")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        width = d.pop("width")

        def _parse_caption(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        caption = _parse_caption(d.pop("caption", UNSET))

        def _parse_thumbnail(data: object) -> None | ThumbnailOut | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                thumbnail_type_0 = ThumbnailOut.from_dict(data)

                return thumbnail_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ThumbnailOut | Unset, data)

        thumbnail = _parse_thumbnail(d.pop("thumbnail", UNSET))

        photo_out = cls(
            content_type=content_type,
            created_at=created_at,
            height=height,
            id=id,
            original_filename=original_filename,
            owner_id=owner_id,
            size_bytes=size_bytes,
            updated_at=updated_at,
            width=width,
            caption=caption,
            thumbnail=thumbnail,
        )

        photo_out.additional_properties = d
        return photo_out

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
