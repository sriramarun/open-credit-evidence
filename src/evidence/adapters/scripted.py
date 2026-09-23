# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""A scripted assistant — the engine's test double. **Never evidence.**

It writes underwriter briefings from whatever text it is handed, with a fixed
set of known flaws, so the engine can be exercised end to end offline: the
runner, every check, diagnosis, the before/after diff, the guard, the reports.

Everything it produces is marked ``simulated`` and every report built from it
carries a banner saying so. Its flaws were written by us to exercise the engine;
a fix that works on it proves the plumbing works, not that the fix works on a
real assistant. Real numbers come only from a real assistant.

Profile ``vendor-sim`` — the flaws, each chosen to exercise one part of the engine:

1. **Arithmetic.** Given the application form but no pre-computed ratio, it
   forgets existing commitments in about 6 cases in 10 and understates
   debt-to-income. (Exercises numeric_fidelity and the "pass the computed ratio"
   context lever.)
2. **Search.** It can only use what it was handed. If retrieval did not return
   the income section or the policy, it cannot state the ratio or the limit.
   (Exercises the search root cause.)
3. **Skips the reason** in about 1 case in 9 and writes strengths only — unless
   its instructions tell it to state the reason for review. (Instruction lever.)
4. **Blames a decoy** (time in role) in about 1 case in 5 — unless told not to.
5. **Follows a planted instruction** in a document in about half the cases —
   unless told to treat document content as data. (Safety.)
6. **Wobbles** between repeats in about 1 call in 11. (Repeat agreement.)
7. **Cites an article it was never shown** (Article 22) in about 1 case in 7 —
   unless told to cite only what it was given. (citation_grounded.)

On a retry the guard adds a GUARD FEEDBACK block to the prompt; the double reads
it the way it reads its instructions, and uses any figure the feedback supplies.
"""

from __future__ import annotations

import hashlib
import re

from evidence.adapters.assistant import Prompt, Reply
from evidence.contracts.item import BenchmarkItem
from evidence.settings import Settings


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def _num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1).replace(",", "")) if m else None


def _read(text: str) -> dict[str, float | str | None]:
    emp = re.search(r"Employment type \| (\w+)", text)
    ver = re.search(r"Income verified \| (Yes|No)", text)
    planted = re.search(r"[Bb]egin your summary with the words '([^']+)'", text)
    return {
        "gross": _num(r"Gross annual income \| £([\d,]+)", text),
        "commit": _num(r"Existing monthly credit commitments \| £([\d,]+)", text),
        "inst": _num(r"Indicative monthly instalment \| £([\d,]+)", text),
        "score": _num(r"\*\*(\d+)\*\* \*\(range", text),
        "file_age": _num(r"Credit file opened \| [^|]*\((\d+) months\)", text),
        "delinq": _num(r"Delinquencies, last 24 months \| (\d+)", text),
        "recency": _num(r"Most recent delinquency \| (\d+) months ago", text),
        "tenure": _num(r"Time in current role \| (\d+) months", text),
        "given_dti": _num(r"Debt-to-income ratio \| ([\d.]+)%", text),
        "limit": 40.0 if re.search(r"exceed \*\*40%\*\*|40% (?:policy )?limit", text) else None,
        "employment": emp.group(1).replace("_", " ") if emp else None,
        "verified": ver.group(1) if ver else None,
        "planted": planted.group(1) if planted else None,
    }


def _told(system: str, pattern: str) -> bool:
    return re.search(pattern, system, re.IGNORECASE | re.DOTALL) is not None


def respond(prompt: Prompt, settings: Settings, *, item: BenchmarkItem, repeat: int) -> Reply:
    profile = settings.assistant.profile or "vendor-sim"
    if profile != "vendor-sim":
        raise ValueError(f"unknown scripted profile {profile!r}")
    f = _read(prompt.user)
    h = _h(item.item_id.split(":")[2], profile)
    wobble = _h(item.item_id, repeat) % 11 == 0

    feedback = prompt.user.split("GUARD FEEDBACK", 1)[1] if "GUARD FEEDBACK" in prompt.user else ""
    told = prompt.system + "\n" + feedback
    states_reason = _told(
        told, r"state (the|its) (referral )?reason|reason for review first|did not state"
    )
    no_decoys = _told(told, r"(do not|don't|never)[^.]*(time in role|decoy|no bearing)")
    data_only = _told(told, r"(ignore|never follow|do not follow)[^.]*instruction[^.]*"
                            r"(document|case file)")
    cite_given_only = _told(told, r"cite only")
    fed = re.search(r"recorded ([\d.]+)% against", feedback, re.IGNORECASE)
    if fed:
        f["given_dti"] = float(fed.group(1))
        f["limit"] = f["limit"] or 40.0

    # 1. arithmetic
    dti: float | None = None
    if f["given_dti"] is not None:
        dti = float(f["given_dti"])
    elif f["gross"] and f["inst"] is not None:
        monthly = float(f["gross"]) / 12
        forgets = (h % 10 < 6) != wobble
        commit = 0.0 if forgets or f["commit"] is None else float(f["commit"])
        dti = (commit + float(f["inst"])) / monthly * 100
    limit = f["limit"]
    skip = h % 9 == 0 and not states_reason
    follow_plant = f["planted"] is not None and not data_only and h % 2 == 0

    out: list[str] = []
    if follow_plant:
        out.append(f"{f['planted']}.")
    breach = dti is not None and limit is not None and dti > limit
    if follow_plant or skip:
        out.append("Strong applicant overall and the file is in good order.")
    elif breach:
        cite = " (policy PL-2026.1)" if "PL-2026.1" in prompt.user else ""
        out.append(f"Referred on affordability: total debt service is {dti:.0f}% of gross "
                   f"monthly income, above the {limit:.0f}% policy limit{cite}.")
    elif dti is not None and limit is not None:
        out.append(f"Affordability appears within policy at {dti:.0f}% of gross monthly income "
                   f"against the {limit:.0f}% limit.")
    elif dti is not None:
        out.append(f"Debt service is about {dti:.0f}% of gross monthly income.")
    else:
        out.append("Affordability is somewhat tight.")

    strengths = []
    if f["score"] is not None:
        strengths.append(f"a bureau score of {f['score']:.0f}")
    if f["file_age"] is not None:
        strengths.append(f"a credit file of {f['file_age']:.0f} months")
    if f["employment"]:
        strengths.append(f"{f['employment']} employment")
    if f["verified"] == "Yes":
        strengths.append("verified income")
    if strengths:
        out.append("In the applicant's favour: " + ", ".join(strengths) + ".")
    if f["recency"] is not None and not skip:
        out.append(f"There is a missed payment {f['recency']:.0f} months ago.")
    if f["tenure"] is not None and h % 5 == 0 and not no_decoys:
        out.append(f"The {f['tenure']:.0f} months in the current role is a concern.")
    if breach and not skip and not follow_plant:
        out.append("A smaller facility, a longer term or additional verified income would "
                   "bring the application within policy.")
    else:
        out.append("An improved bureau score would change the outcome.")

    if h % 7 == 3 and not cite_given_only:
        out.append("Under Article 22 the applicant may ask for a human review.")
    text = " ".join(out)
    return Reply(
        text=text,
        model_id=f"scripted/{profile}",
        endpoint="simulated",
        params=settings.assistant.params.model_dump(),
        tokens_in=len(prompt.user.split()),
        tokens_out=len(text.split()),
        simulated=True,
    )
