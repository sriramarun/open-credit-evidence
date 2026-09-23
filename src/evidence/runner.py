# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The runner — puts every case to the assistant, N times, and records exactly what was said.

    run = run_pack(pack, settings, out_dir, split="proof")

Writes, under ``out_dir/<run_id>/``:

- ``run_manifest.json`` — pack, settings hash, engine version, counts
- ``settings.yaml``     — the exact settings, so the run can be reproduced
- ``transcripts.jsonl`` — one line per call, appended as it goes
- ``results.jsonl``     — every check on every transcript, rebuilt at the end
- ``errors.jsonl``      — calls that failed after retries, if any

Resumable: a killed run picks up where it stopped, because each
(item, repeat) already in ``transcripts.jsonl`` is skipped. Rate-limited: at
most ``rpm`` calls per minute (NVIDIA Build allows 40). Deterministic order:
items in pack order, repeats in sequence.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from evidence import __version__
from evidence.adapters.assistant import build_prompt, call, prompt_version
from evidence.checks import run_checks
from evidence.contracts.item import BenchmarkItem
from evidence.contracts.run import RunManifest
from evidence.contracts.transcript import SUTPins, Transcript
from evidence.packs import CasePack
from evidence.settings import Settings


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def engine_git() -> str | None:
    try:
        root = Path(__file__).resolve().parents[2]
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "src"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}" if sha else None
    except (OSError, subprocess.SubprocessError):
        return None


def _corpus_sha(settings: Settings) -> str | None:
    if not settings.corpus.path or settings.corpus.top_k <= 0:
        return None
    from evidence.corpus import load_corpus

    return load_corpus(settings.corpus.path).sha256


def default_run_id(settings: Settings, pack: CasePack, split: str | None) -> str:
    return f"{settings.name}-{split or 'all'}-{settings.sha256()[:8]}-{pack.items_sha256[:8]}"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_transcript(t: Transcript, item: BenchmarkItem) -> list[dict]:
    """Every check the item asks for, on one transcript, as result records."""
    out = []
    for r in run_checks(item.deterministic_checks, output=t.output, item=item,
                        prompt=t.user_prompt):
        out.append({
            "result_id": f"{t.sha256[:12]}:{r.name}",
            "item_id": t.item_id,
            "repeat": t.repeat,
            "transcript_sha256": t.sha256,
            "check": r.name,
            **r.to_score(),
        })
    return out


def rebuild_results(run_dir: Path, pack: CasePack) -> list[dict]:
    transcripts = [Transcript.model_validate(d) for d in _read_jsonl(run_dir / "transcripts.jsonl")]
    results: list[dict] = []
    for t in transcripts:
        results.extend(check_transcript(t, pack.item(t.item_id)))
    with (run_dir / "results.jsonl").open("w") as fh:
        for r in results:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    return results


def run_pack(
    pack: CasePack,
    settings: Settings,
    out_dir: str | Path,
    *,
    split: str | None = None,
    repeats: int | None = None,
    limit: int | None = None,
    rpm: float | None = None,
    run_id: str | None = None,
    max_retries: int = 3,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path, RunManifest]:
    repeats = repeats or settings.repeats
    # The 40/minute limit is the hosted API's; local callables and the test double run free.
    rpm = rpm if rpm is not None else (40 if settings.assistant.adapter == "openai" else 0)
    items = pack.select(split, limit)
    run_id = run_id or default_run_id(settings, pack, split)
    run_dir = Path(out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = RunManifest.model_validate_json(manifest_path.read_text())
        if manifest.settings_sha256 != settings.sha256():
            raise ValueError(f"{run_dir} was started with different settings; use a new run id")
    else:
        manifest = RunManifest(
            run_id=run_id, pack_id=pack.pack_id, pack_items_sha256=pack.items_sha256,
            settings_name=settings.name, settings_sha256=settings.sha256(),
            corpus_sha256=_corpus_sha(settings),
            engine_version=__version__, engine_git=engine_git(), repeats=repeats, split=split,
            item_ids=[i.item_id for i in items], simulated=settings.simulated, started_at=now(),
        )
    manifest.calls_planned = len(items) * repeats
    (run_dir / "settings.yaml").write_text(settings.to_yaml())

    t_path = run_dir / "transcripts.jsonl"
    done = {(d["item_id"], d["repeat"]) for d in _read_jsonl(t_path)}
    interval = 60.0 / rpm if rpm else 0.0
    last_call = 0.0
    settings_sha = settings.sha256()

    with t_path.open("a") as tf, (run_dir / "errors.jsonl").open("a") as ef:
        for item in items:
            for rep in range(repeats):
                if (item.item_id, rep) in done:
                    continue
                prompt = build_prompt(item, settings)
                for attempt in range(1, max_retries + 1):
                    wait = interval - (time.monotonic() - last_call)
                    if wait > 0:
                        time.sleep(wait)
                    last_call = time.monotonic()
                    started = now()
                    try:
                        reply = call(prompt, settings, item=item, repeat=rep)
                        break
                    except Exception as exc:  # noqa: BLE001 — record, back off, retry
                        if attempt == max_retries:
                            ef.write(json.dumps({"item_id": item.item_id, "repeat": rep,
                                                 "error": repr(exc), "at": now()}) + "\n")
                            ef.flush()
                            reply = None
                        else:
                            time.sleep(2 ** attempt)
                if reply is None:
                    continue
                pins = SUTPins(model_id=reply.model_id,
                               prompt_version=prompt_version(prompt.system),
                               params=reply.params, settings_sha256=settings_sha,
                               endpoint=reply.endpoint)
                t = Transcript(
                    item_id=item.item_id, run_id=run_id, repeat=rep, sut=pins,
                    system_prompt=prompt.system, user_prompt=prompt.user,
                    retrieved=prompt.retrieved, output=reply.text,
                    latency_ms=reply.latency_ms, tokens_in=reply.tokens_in,
                    tokens_out=reply.tokens_out, provider_id=reply.provider_id,
                    simulated=reply.simulated, started_at=started,
                    sha256=Transcript.content_hash(item.item_id, rep, pins, prompt.system,
                                                   prompt.user, reply.text),
                )
                tf.write(t.model_dump_json() + "\n")
                tf.flush()
                done.add((item.item_id, rep))
                if progress:
                    progress(f"{item.item_id} r{rep}")

    manifest.calls_done = len(done)
    manifest.finished_at = now()
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")
    rebuild_results(run_dir, pack)
    return run_dir, manifest
