# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Deterministic checks — grading that needs no model and no rubric argument.

Every check is domain-agnostic. If a check here needs to know what a "loan"
is, the abstraction has failed. Checks resolve model output against the
reference lists an item carries; they never see the answer key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem

CheckFn = Callable[..., CheckResult]
_REGISTRY: dict[str, CheckFn] = {}


def check(name: str) -> Callable[[CheckFn], CheckFn]:
    """Register a check under the name items refer to it by."""

    def register(fn: CheckFn) -> CheckFn:
        _REGISTRY[name] = fn
        fn.check_name = name  # type: ignore[attr-defined]
        return fn

    return register


def available_checks() -> list[str]:
    return sorted(_REGISTRY)


def run_checks(names: list[str], *, output: str, item: BenchmarkItem) -> list[CheckResult]:
    """Run the named checks against one model output."""
    results: list[CheckResult] = []
    for name in names:
        try:
            fn = _REGISTRY[name]
        except KeyError as exc:
            raise KeyError(f"unknown check {name!r}; available: {available_checks()}") from exc
        results.append(fn(output=output, item=item))
    return results


def _load_all() -> None:
    # Importing registers. Kept explicit so a missing module is a loud failure.
    from evidence.checks import omission  # noqa: F401


_load_all()

__all__: list[Any] = ["CheckResult", "available_checks", "check", "run_checks"]
