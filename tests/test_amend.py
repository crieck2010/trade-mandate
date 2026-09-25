"""Tests for amendments-as-law: propose, ratify, history, verify, tamper."""

import json
import os

import pytest

from trade_mandate.amend import MandateStore


@pytest.fixture()
def store(tmp_path):
    return MandateStore(str(tmp_path))


def test_create_requires_signoff(store):
    with pytest.raises(ValueError):
        store.create("h", approver="", rationale="x", effective_date="2026-01-01")
    with pytest.raises(ValueError):
        store.create("h", approver="C", rationale="", effective_date="2026-01-01")
    with pytest.raises(ValueError):
        store.create("h", approver="C", rationale="x", effective_date="")


def test_create_writes_json_and_md(store):
    r = store.create("house", approver="Charlie", rationale="genesis",
                     effective_date="2026-09-24")
    assert r["version"] == 1
    assert os.path.isfile(store.json_path("house"))
    assert os.path.isfile(store.md_path("house"))
    assert len(r["json_sha256"]) == 64 and len(r["md_sha256"]) == 64


def test_create_twice_refused(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    with pytest.raises(ValueError):
        store.create("house", approver="C", rationale="g2",
                     effective_date="2026-09-25")


def test_propose_and_ratify(store):
    store.create("house", approver="Charlie", rationale="genesis",
                 effective_date="2026-09-24")
    a = store.propose_amendment("house", {"max_drawdown": 0.12},
                                proposer="Charlie")
    assert a["status"] == "pending"
    assert a["base_version"] == 1
    assert store.pending_amendments("house")[0]["amendment_id"] == a["amendment_id"]

    r = store.ratify("house", a["amendment_id"], approver="Charlie",
                     rationale="tighter leash", effective_date="2026-09-25")
    assert r["version"] == 2
    assert store.load("house")["max_drawdown"] == 0.12
    assert store.pending_amendments("house") == []


def test_ratify_requires_signoff(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    a = store.propose_amendment("house", {"max_drawdown": 0.12}, proposer="C")
    with pytest.raises(ValueError):
        store.ratify("house", a["amendment_id"], approver="",
                     rationale="x", effective_date="2026-09-25")
    with pytest.raises(ValueError):
        store.ratify("house", a["amendment_id"], approver="C",
                     rationale="", effective_date="2026-09-25")
    with pytest.raises(ValueError):
        store.ratify("house", a["amendment_id"], approver="C",
                     rationale="x", effective_date="")
    # still pending after refused ratifications
    assert len(store.pending_amendments("house")) == 1


def test_ratify_unknown_amendment_refused(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    with pytest.raises(ValueError):
        store.ratify("house", "house-a99", approver="C",
                     rationale="x", effective_date="2026-09-25")


def test_ratify_rejects_invalid_resulting_mandate(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    a = store.propose_amendment("house", {"max_drawdown": 9.9}, proposer="C")
    with pytest.raises(ValueError):
        store.ratify("house", a["amendment_id"], approver="C",
                     rationale="x", effective_date="2026-09-25")


def test_history_ordering(store):
    store.create("house", approver="C", rationale="g1", effective_date="2026-09-24")
    a = store.propose_amendment("house", {"max_drawdown": 0.12}, proposer="C")
    store.ratify("house", a["amendment_id"], approver="C", rationale="g2",
                 effective_date="2026-09-25")
    hist = store.history("house")
    assert [h["version"] for h in hist] == [1, 2]
    assert hist[0]["action"] == "create" and hist[1]["action"] == "amend"
    assert hist[1]["approver"] == "C"


def test_verify_clean(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    v = store.verify("house")
    assert v["ok"] is True
    assert v["tampered_files"] == []
    assert v["payload_checksum_ok"] is True


def test_verify_detects_json_tamper(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    with open(store.json_path("house"), "a") as fh:
        fh.write(" ")
    v = store.verify("house")
    assert v["ok"] is False
    assert "json_sha256" in v["tampered_files"]


def test_verify_detects_md_tamper(store):
    store.create("house", approver="C", rationale="g", effective_date="2026-09-24")
    with open(store.md_path("house"), "a") as fh:
        fh.write("\n<!-- sneaky -->")
    v = store.verify("house")
    assert v["ok"] is False
    assert "md_sha256" in v["tampered_files"]


def test_verify_unknown_policy_raises(store):
    with pytest.raises(FileNotFoundError):
        store.verify("nope")


def test_load_unknown_raises(store):
    with pytest.raises(FileNotFoundError):
        store.load("nope")
