# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Public-key signatures on evidence packs, with OpenSSH.

    evidence sign   evidence/<pack> --key ~/.ssh/id_ed25519 --identity jane@bank.example
    evidence verify evidence/<pack> --allowed-signers settings/allowed_signers

The HMAC seal proves a pack was not altered by anyone without the shared key, but
anyone holding the key can seal. A signature proves *who*: it is made with a
private key only the signer holds, and checked against a list of public keys the
bank trusts (an OpenSSH ``allowed_signers`` file).

Uses ``ssh-keygen -Y sign`` / ``-Y verify``, which ships with OpenSSH on every
Linux and macOS machine, so no extra dependency and no network. The signature
covers ``CHECKSUMS.json``, which covers every file, so it covers the whole pack.
It is written next to it as ``CHECKSUMS.json.sig``.

A signature means the named person produced or approved exactly these files.
It is not a professional opinion that the assistant is fit for use.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

NAMESPACE = "evidence-pack"
SIG_NAME = "CHECKSUMS.json.sig"


def available() -> bool:
    return shutil.which("ssh-keygen") is not None


def sign(pack_dir: str | Path, key: str | Path) -> Path:
    pack_dir = Path(pack_dir)
    target = pack_dir / "CHECKSUMS.json"
    sig = pack_dir / SIG_NAME
    sig.unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(target)],
                   check=True, capture_output=True, text=True)
    return sig


def verify_signature(pack_dir: str | Path, allowed_signers: str | Path) -> tuple[bool, str]:
    """(ok, message). The message names the signer when the signature is good."""
    pack_dir = Path(pack_dir)
    sig = pack_dir / SIG_NAME
    if not sig.exists():
        return False, "not signed"
    # the signer's identity is whichever principal in allowed_signers the key matches
    found = subprocess.run(["ssh-keygen", "-Y", "find-principals", "-s", str(sig),
                            "-f", str(allowed_signers)], capture_output=True, text=True)
    if found.returncode != 0 or not found.stdout.strip():
        return False, "signed by a key that is not in the allowed signers file"
    principal = found.stdout.strip().splitlines()[0]
    with (pack_dir / "CHECKSUMS.json").open("rb") as data:
        res = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers),
                              "-I", principal, "-n", NAMESPACE, "-s", str(sig)],
                             stdin=data, capture_output=True, text=True)
    if res.returncode != 0:
        return False, f"signature does not match CHECKSUMS.json ({res.stderr.strip()[:120]})"
    return True, f"signed by {principal}"
