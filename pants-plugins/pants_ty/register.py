from __future__ import annotations

from collections.abc import Iterable

from pants.engine.rules import Rule
from pants.engine.unions import UnionRule

from pants_ty import rules as ty_rules
from pants_ty import skip_field, subsystem


def rules() -> Iterable[Rule | UnionRule]:
    return (*subsystem.rules(), *skip_field.rules(), *ty_rules.rules())
