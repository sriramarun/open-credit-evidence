# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Writing an evidence pack from a finished run.

    write_evidence_pack(run_dir, pack, out_dir, attester="Jane Doe, Model Risk")

Copies the inputs, derives everything else (``evidence.derive``), then writes
``CHECKSUMS.json``: the sha256 of every file, a root hash over that list, an
attestation block, and — if a sealing key is set — an HMAC-SHA256 seal over the
root.

About the seal: HMAC proves the pack was not altered by anyone who lacks the
key. It does not prove who produced it — anyone holding the key can seal. A
public-key signature (Sigstore, GPG) is the stronger form and is planned; the
field names leave room for it.

About the attestation: it names the person who stands behind the pack and says
what they are attesting to. A seal proves nothing has changed since sealing; it
is not a professional opinion, and the wording never suggests it is.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
from importlib import resources
from pathlib import Path

from evidence.derive import derive, dump_json, load_inputs
from evidence.packs import CasePack

CHECKSUMS = "CHECKSUMS.json"
SEAL_ENV = "EVIDENCE_SEAL_KEY"

ATTESTATION_STATEMENT = (
    "I have reviewed this evidence pack. The seal shows the files have not changed since "
    "it was sealed. It is not an opinion on whether the assistant is compliant with any "
    "regulation, and it describes only the constructed cases listed in items.jsonl."
)


def default_thresholds() -> str:
    return resources.files("evidence").joinpath("defaults/thresholds.yaml").read_text()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root_hash(files: dict[str, str]) -> str:
    listing = json.dumps(dict(sorted(files.items())), separators=(",", ":"))
    return hashlib.sha256(listing.encode()).hexdigest()


def seal(root: str, key: str) -> str:
    return hmac.new(key.encode(), root.encode(), hashlib.sha256).hexdigest()


def write_checksums(out: Path, *, attester: str | None, seal_key: str | None) -> dict:
    (out / "attestation.json").write_bytes(dump_json({
        "attester": attester,
        "statement": ATTESTATION_STATEMENT if attester else None,
    }))
    files = {
        str(p.relative_to(out)): sha256_file(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name not in (CHECKSUMS, "CHECKSUMS.json.sig")
    }
    root = root_hash(files)
    body = {
        "algorithm": "sha256",
        "files": files,
        "root": root,
        "seal": {"method": "hmac-sha256", "value": seal(root, seal_key)} if seal_key else None,
    }
    (out / CHECKSUMS).write_bytes(dump_json(body))
    (out / "CHECKSUMS.json.sig").unlink(missing_ok=True)  # any old signature no longer applies
    return body


def write_evidence_pack(
    run_dir: str | Path,
    pack: CasePack,
    out_dir: str | Path,
    *,
    thresholds: str | Path | None = None,
    attester: str | None = None,
    seal_key: str | None = None,
) -> Path:
    run_dir, out = Path(run_dir), Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    shutil.copyfile(pack.root / "items.jsonl", out / "items.jsonl")
    shutil.copyfile(pack.root / "manifest.json", out / "pack_manifest.json")
    ob = pack.root / pack.manifest.get("obligations_file", "obligations.yaml")
    shutil.copyfile(ob, out / "obligations.yaml")
    for name in ("run_manifest.json", "settings.yaml", "transcripts.jsonl"):
        shutil.copyfile(run_dir / name, out / name)
    (out / "thresholds.yaml").write_text(
        Path(thresholds).read_text() if thresholds else default_thresholds()
    )

    for rel, body in derive(load_inputs(out)).items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    write_checksums(out, attester=attester, seal_key=seal_key or os.environ.get(SEAL_ENV))
    return out
