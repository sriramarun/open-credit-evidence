# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Where each role runs is a .env decision; the adapter must honour it without a network."""

import os

import pytest

from evidence.adapters import nvidia_build as nb


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("EVIDENCE_") or k == "NO_PROXY" or k == "no_proxy":
            monkeypatch.delenv(k, raising=False)


def test_defaults_to_build():
    ep = nb.endpoint_for("assistant")
    assert ep.base_url == nb.BASE_URL
    assert ep.model_id == nb.MODELS["assistant"]
    assert ep.is_build


def test_role_override_points_at_nim(monkeypatch):
    monkeypatch.setenv("EVIDENCE_ASSISTANT_BASE_URL", "http://rtx-3se-05-36:8000/v1/")
    monkeypatch.setenv("EVIDENCE_ASSISTANT_MODEL", "nvidia/nemotron-3.5-lightning")
    ep = nb.endpoint_for("assistant")
    assert ep.base_url == "http://rtx-3se-05-36:8000/v1"
    assert ep.model_id == "nvidia/nemotron-3.5-lightning"
    assert not ep.is_build
    # other roles untouched
    assert nb.endpoint_for("judge").is_build


def test_deprecated_model_refused_even_when_overridden(monkeypatch):
    monkeypatch.setenv("EVIDENCE_JUDGE_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    with pytest.raises(ValueError, match="deprecated"):
        nb.endpoint_for("judge")


def test_unknown_role():
    with pytest.raises(KeyError):
        nb.endpoint_for("retriever")


def test_local_host_is_added_to_no_proxy(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    nb._bypass_proxy("http://rtx-3se-05-36:8000/v1")
    assert os.environ["NO_PROXY"] == "localhost,127.0.0.1,rtx-3se-05-36"
    nb._bypass_proxy("http://rtx-3se-05-36:8000/v1")  # idempotent
    assert os.environ["NO_PROXY"].count("rtx-3se-05-36") == 1


def test_build_host_never_touches_proxy(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost")
    nb._bypass_proxy(nb.BASE_URL)
    assert os.environ["NO_PROXY"] == "localhost"
