# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The frozen interfaces between the pack side and the engine side.

See BUILD.md §4. These are the two formats Sriram and Clyde share, proposed
here for the Friday freeze. Nothing else in the repository may define its own
version of them.
"""

from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem, GradingSpec, ItemContext
from evidence.contracts.transcript import Retrieved, SUTPins, Transcript

__all__ = [
    "BenchmarkItem", "CheckResult", "GradingSpec", "ItemContext",
    "Retrieved", "SUTPins", "Transcript",
]
