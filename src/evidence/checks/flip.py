# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``flip_accuracy`` — did the briefing say what would change the outcome, correctly?

The pack lists the levers that would move a case, by field and direction only —
never the threshold. The briefing passes if it names at least one of those
levers with the right direction ("a smaller facility", "additional verified
income"), and fails if it names none, or only in the wrong direction.

Direction is read from the words within a few words of the lever's name, in
the same sentence, so "a smaller facility or higher income" credits both levers
correctly and a direction word in the next sentence never does.
"""

from __future__ import annotations

import re
from typing import Any

from evidence.checks import check
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem

UP = frozenset(
    "increase increased increasing higher more additional larger greater raise raised "
    "longer extend extended extending boost improved improve improving".split()
)
DOWN = frozenset(
    "decrease decreased reduce reduced reducing reduction lower smaller less fewer shorter "
    "cut clear cleared repay repaid".split()
)
WINDOW = 4


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _direction_near(words: list[str], start: int, end: int) -> set[str]:
    near = words[max(0, start - WINDOW): end + WINDOW]
    found = set()
    if UP & set(near):
        found.add("increase")
    if DOWN & set(near):
        found.add("decrease")
    return found


def _find(words: list[str], alias: str) -> list[tuple[int, int]]:
    a = _words(alias)
    n = len(a)
    return [(i, i + n) for i in range(len(words) - n + 1) if words[i: i + n] == a] if n else []


@check("flip_accuracy")
def flip_accuracy(*, output: str, item: BenchmarkItem, **_: Any) -> CheckResult:
    g = item.grading
    if not g.flip_refs:
        return CheckResult(name="flip_accuracy", passed=True, score=1.0,
                           detail="no lever declared for this item")
    sentences = [_words(s) for s in re.split(r"(?<=[.!?;])\s+|\n+", output) if s.strip()]
    evidence: list[dict[str, Any]] = []
    right = 0
    for fr in g.flip_refs:
        best = None
        for alias in g.flip_aliases.get(fr.ref, [fr.ref.replace("_", " ")]):
            hits = [(ws, s, e) for ws in sentences for s, e in _find(ws, alias)]
            for ws, s, e in hits:
                dirs = _direction_near(ws, s, e)
                if fr.direction in dirs:
                    best = {"ref": fr.ref, "alias": alias, "direction": fr.direction,
                            "ok": True}
                    break
                best = best or {"ref": fr.ref, "alias": alias, "direction_found": sorted(dirs),
                                "direction": fr.direction, "ok": False}
            if best and best["ok"]:
                break
        if best:
            evidence.append(best)
            right += int(best["ok"])
        else:
            evidence.append({"ref": fr.ref, "direction": fr.direction, "ok": False,
                             "mentioned": False})
    passed = right > 0
    detail = (
        f"named {right} valid lever(s) with the right direction"
        if passed
        else "named no lever that would change the outcome, or only in the wrong direction"
    )
    return CheckResult(name="flip_accuracy", passed=passed, score=1.0 if passed else 0.0,
                       detail=detail, evidence=evidence)
