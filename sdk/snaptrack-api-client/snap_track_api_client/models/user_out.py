from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UserOut")


@_attrs_define
class UserOut:
    """
    Attributes:
        created_at (datetime.datetime):
        email (str):
        id (int):
        is_active (bool):
        is_admin (bool):
    """

    created_at: datetime.datetime
    email: str
    id: int
    is_active: bool
    is_admin: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        email = self.email

        id = self.id

        is_active = self.is_active

        is_admin = self.is_admin

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "email": email,
                "id": id,
                "is_active": is_active,
                "is_admin": is_admin,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        email = d.pop("email")

        id = d.pop("id")

        is_active = d.pop("is_active")

        is_admin = d.pop("is_admin")

        user_out = cls(
            created_at=created_at,
            email=email,
            id=id,
            is_active=is_active,
            is_admin=is_admin,
        )

        user_out.additional_properties = d
        return user_out

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
