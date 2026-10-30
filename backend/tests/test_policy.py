import pytest
from app.auth.policy import Capability, Membership, Role, permitted


@pytest.mark.parametrize("role, expected", [
    (Role.VIEWER, {Capability.READ}),
    (Role.PLANNER, {Capability.READ, Capability.PIN, Capability.VOTE}),
    (Role.LEADER, {Capability.READ, Capability.PIN, Capability.VOTE, Capability.LEAD}),
])
def test_trip_role_matrix(role, expected):
    member = Membership(role)
    assert {cap for cap in Capability if permitted(cap, is_admin=False, membership=member)} == expected


def test_admin_does_not_bypass_membership_and_removed_member_has_no_trip_capability():
    for membership in (None, Membership(Role.LEADER, active=False)):
        assert not any(permitted(cap, is_admin=True, membership=membership) for cap in
                       (Capability.READ, Capability.PIN, Capability.VOTE, Capability.LEAD))
        assert permitted(Capability.DATASETS, is_admin=True, membership=membership)


def test_vote_only_planner_cannot_pin():
    membership = Membership(Role.PLANNER, can_pin=False)
    assert permitted(Capability.VOTE, is_admin=False, membership=membership)
    assert not permitted(Capability.PIN, is_admin=False, membership=membership)
