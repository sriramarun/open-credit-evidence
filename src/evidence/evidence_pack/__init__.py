# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The evidence pack: writing it, and verifying it has not been altered."""

from evidence.evidence_pack.verify import VerifyReport, verify
from evidence.evidence_pack.writer import write_evidence_pack

__all__ = ["VerifyReport", "verify", "write_evidence_pack"]
