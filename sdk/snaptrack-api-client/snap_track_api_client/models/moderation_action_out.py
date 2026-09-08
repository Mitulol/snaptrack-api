from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.moderation_decision import ModerationDecision

T = TypeVar("T", bound="ModerationActionOut")


@_attrs_define
class ModerationActionOut:
    """
    Attributes:
        created_at (datetime.datetime):
        decision (ModerationDecision):
        flag_id (int):
        id (int):
        moderator_id (int | None):
        note (None | str):
        photo_id (int):
    """

    created_at: datetime.datetime
    decision: ModerationDecision
    flag_id: int
    id: int
    moderator_id: int | None
    note: None | str
    photo_id: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        decision = self.decision.value

        flag_id = self.flag_id

        id = self.id

        moderator_id: int | None
        moderator_id = self.moderator_id

        note: None | str
        note = self.note

        photo_id = self.photo_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "decision": decision,
                "flag_id": flag_id,
                "id": id,
                "moderator_id": moderator_id,
                "note": note,
                "photo_id": photo_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        decision = ModerationDecision(d.pop("decision"))

        flag_id = d.pop("flag_id")

        id = d.pop("id")

        def _parse_moderator_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        moderator_id = _parse_moderator_id(d.pop("moderator_id"))

        def _parse_note(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        note = _parse_note(d.pop("note"))

        photo_id = d.pop("photo_id")

        moderation_action_out = cls(
            created_at=created_at,
            decision=decision,
            flag_id=flag_id,
            id=id,
            moderator_id=moderator_id,
            note=note,
            photo_id=photo_id,
        )

        moderation_action_out.additional_properties = d
        return moderation_action_out

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
