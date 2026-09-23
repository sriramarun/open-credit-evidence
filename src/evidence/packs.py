# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Loading a case pack — and refusing one that has been altered.

A pack is a folder with ``items.jsonl``, ``manifest.json`` and
``obligations.yaml``. The manifest records the sha256 of ``items.jsonl``; if the
file no longer matches, the loader refuses it. A pack edited after it was built
can no longer be trusted to carry the marking key it claims.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from evidence.contracts.item import BenchmarkItem


class PackTampered(ValueError):
    pass


@dataclass(frozen=True)
class CasePack:
    root: Path
    manifest: dict
    items: list[BenchmarkItem]
    obligations: dict
    items_sha256: str

    @property
    def pack_id(self) -> str:
        return self.manifest["pack_id"]

    def select(self, split: str | None = None, limit: int | None = None) -> list[BenchmarkItem]:
        chosen = [i for i in self.items if split is None or i.tags.get("split") == split]
        return chosen[:limit] if limit else chosen

    def item(self, item_id: str) -> BenchmarkItem:
        for i in self.items:
            if i.item_id == item_id:
                return i
        raise KeyError(item_id)


def load_pack(root: str | Path) -> CasePack:
    root = Path(root)
    raw = (root / "items.jsonl").read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("items_sha256") != sha:
        raise PackTampered(
            f"{root}/items.jsonl does not match its manifest "
            f"(manifest {manifest.get('items_sha256', '?')[:12]}…, file {sha[:12]}…)"
        )
    items = [BenchmarkItem.model_validate_json(line) for line in raw.decode().splitlines() if line]
    ob_path = root / manifest.get("obligations_file", "obligations.yaml")
    obligations = yaml.safe_load(ob_path.read_text()) if ob_path.exists() else {}
    return CasePack(root=root, manifest=manifest, items=items, obligations=obligations,
                    items_sha256=sha)
