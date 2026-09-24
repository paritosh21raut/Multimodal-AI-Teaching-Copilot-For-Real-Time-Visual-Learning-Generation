from __future__ import annotations

from typing import List

from app.importance.importance_types import DevelopmentalRole


def order_roles(roles: List[str]) -> List[str]:
    """
    Canonical, deterministic ordering of developmental roles.

    Unknown entries are dropped unless the input was empty or contained
    only UNKNOWN, in which case [UNKNOWN] is preserved.
    """
    canonical = [
        DevelopmentalRole.INTRODUCTION.value,
        DevelopmentalRole.DEFINITION.value,
        DevelopmentalRole.PROPERTY.value,
        DevelopmentalRole.RELATIONSHIP.value,
        DevelopmentalRole.MECHANISM.value,
        DevelopmentalRole.PROCEDURE.value,
        DevelopmentalRole.EXAMPLE.value,
        DevelopmentalRole.APPLICATION.value,
        DevelopmentalRole.EXCEPTION.value,
        DevelopmentalRole.SYNTHESIS.value,
        DevelopmentalRole.META.value,
    ]

    if not roles:
        return [DevelopmentalRole.UNKNOWN.value]

    seen = {r for r in roles if r in canonical}
    ordered = [r for r in canonical if r in seen]

    if not ordered:
        return [DevelopmentalRole.UNKNOWN.value]
    return ordered