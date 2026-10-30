"""Shared account and trip capability rules, independent of transport."""
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    PLANNER = "planner"
    LEADER = "leader"


class Capability(StrEnum):
    READ = "read"
    PIN = "pin"
    VOTE = "vote"
    LEAD = "lead"
    DATASETS = "datasets"


@dataclass(frozen=True)
class Membership:
    role: Role
    active: bool = True
    can_pin: bool = True


def permitted(capability: Capability, *, is_admin: bool, membership: Membership | None) -> bool:
    if capability == Capability.DATASETS:
        return is_admin
    if membership is None or not membership.active:
        return False
    if capability == Capability.READ:
        return True
    if capability == Capability.PIN:
        return membership.role == Role.LEADER or (membership.role == Role.PLANNER and membership.can_pin)
    if capability == Capability.VOTE:
        return membership.role in (Role.PLANNER, Role.LEADER)
    if capability == Capability.LEAD:
        return membership.role == Role.LEADER
    return False
