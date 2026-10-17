"""Separate reviewer payload/permission/contribution/confirmation/retry guards."""

import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cli import muj_naming_approval as cli
from app.cli import muj_publication as original
from app.cli.indoor_demo import DemoError
from tests.unit.test_muj_naming_submit import prepared as prepared_fixture


@pytest.fixture
def approval(tmp_path, monkeypatch):
    p = prepared_fixture.__wrapped__(tmp_path, monkeypatch)
    owner = p.client.session["user_id"]
    actor, submission, creation = map(str, (uuid4(), uuid4(), uuid4()))
    reviewer_reasons = {
        k: "Explicit reviewer candidate reasoning, separate from submitter text."
        for k in p.payload["acknowledgements"]
    }
    p.report.update(reviewer_proposed_reasons=reviewer_reasons, creation_audit={"id": creation})
    p.current.update(deepcopy(p.report))
    sub = dict(
        id=submission,
        status="submitted",
        submitter_id=owner,
        validation_id=p.report["validation_id"],
        checksum=p.report["checksum"],
        edit_version=4,
        acknowledgements=deepcopy(p.payload["acknowledgements"]),
        decisions=[],
    )
    p.current.update(version=4, status="review", existing_submissions=[sub])
    cli.persist(p.folder / "report.json", p.report)
    selected = {
        "validation_id": p.report["validation_id"],
        "acknowledgements": deepcopy(reviewer_reasons),
    }
    cli.persist(p.folder / "reviewer-proposal.json", selected)
    session = dict(
        user_id=actor,
        username="muj-reviewer",
        grants=[
            dict(
                campus_id=str(cli.CAMPUS_ID),
                permissions=["review_read", "review_decide", "audit_read"],
            )
        ],
    )
    events = [
        dict(id=creation, revision_id=p.report["draft_id"], actor_id=owner, action="draft.create")
    ]
    p.client.session = {"user_id": actor}

    def request(method, path, payload=None, *, headers=None, query=None):
        if method == "GET":
            return deepcopy(session if path.endswith("/session") else events)
        assert method == "POST" and path.endswith(f"/submissions/{submission}/decision")
        assert headers == {"If-Match": '"4"'} and payload["decision"] == "approve"
        p.posts.append(deepcopy(payload))
        p.current.update(version=5)
        sub.update(
            status="approved",
            edit_version=5,
            decisions=[dict(id=str(uuid4()), actor_id=actor, **deepcopy(payload))],
        )
        return {"status": "approved", "edit_version": 5}

    p.client.request = request
    monkeypatch.setattr(
        cli, "get_settings", lambda: SimpleNamespace(storage_root=p.folder.parents[4])
    )
    monkeypatch.setattr(cli, "collect", lambda *args: deepcopy(p.current))
    args = (
        p.client,
        p.report["draft_id"],
        p.report["validation_id"],
        submission,
        p.folder,
        p.report["checksum"],
    )
    return SimpleNamespace(
        p=p,
        args=args,
        selected=selected,
        session=session,
        events=events,
        sub=sub,
        journal=p.folder / "approval" / actor / submission,
    )


@pytest.mark.parametrize(
    "change", ["missing", "extra", "blank", "short", "wrong-validation", "duplicate"]
)
def test_invalid_reviewer_proposal_never_uses_submitter_fallback(approval, change):
    a = approval
    if change == "missing":
        a.selected["acknowledgements"].pop("0")
    elif change == "extra":
        a.selected["acknowledgements"]["old"] = "Preserved stale reviewer text."
    elif change == "blank":
        a.selected["acknowledgements"]["0"] = "   "
    elif change == "short":
        a.selected["acknowledgements"]["0"] = "yes"
    elif change == "wrong-validation":
        a.selected["validation_id"] = str(uuid4())
    path = a.p.folder / "reviewer-proposal.json"
    cli.persist(path, a.selected)
    if change == "duplicate":
        path.write_text('{"validation_id":"a","validation_id":"b"}')
    before = path.read_bytes()
    with pytest.raises(DemoError):
        cli.approve(*a.args, notes_input=lambda _: pytest.fail("Before notes"))
    assert not a.p.posts and path.read_bytes() == before


@pytest.mark.parametrize(
    "change",
    [
        "username",
        "submitter",
        "permission",
        "campus",
        "contributor",
        "audit-bound",
        "submission",
        "checksum",
        "proof",
        "version",
    ],
)
def test_reviewer_and_exact_current_submission_guards(approval, monkeypatch, change):
    a = approval
    if change == "username":
        a.session["username"] = "owner"
    elif change == "submitter":
        a.sub["submitter_id"] = a.session["user_id"]
    elif change == "permission":
        a.session["grants"][0]["permissions"] = ["review_read", "audit_read"]
    elif change == "campus":
        a.session["grants"][0]["campus_id"] = str(uuid4())
    elif change == "contributor":
        a.events.append(
            dict(
                id=str(uuid4()),
                revision_id=a.p.report["draft_id"],
                actor_id=a.session["user_id"],
                action="graph.patch",
            )
        )
    elif change == "audit-bound":
        a.events.clear()
    elif change == "submission":
        a.sub["id"] = str(uuid4())
    elif change == "checksum":
        a.sub["checksum"] = "b" * 64
    elif change == "proof":
        a.p.current["sources"] = {"modified": {}}
    elif change == "version":
        a.sub["edit_version"] = 3
    with pytest.raises(DemoError):
        cli.approve(*a.args, notes_input=lambda _: pytest.fail("Before notes"))
    assert not a.p.posts


@pytest.mark.parametrize(
    "change", ["cancel", "proposal", "report", "proof", "version", "permission"]
)
def test_confirmation_races_and_cancel_preserve_input(approval, change):
    a = approval

    def confirm(_):
        if change == "cancel":
            return "APPROVE"
        if change == "proposal":
            a.selected["acknowledgements"]["0"] = (
                "Retain edited reviewer rationale during confirmation."
            )
            cli.persist(a.p.folder / "reviewer-proposal.json", a.selected)
        elif change == "report":
            (a.p.folder / "report.json").write_text("{}")
        elif change == "proof":
            a.p.current["original_imports"] = ["changed"]
        elif change == "version":
            a.p.current.update(version=5)
            a.sub.update(edit_version=5)
        elif change == "permission":
            a.session["grants"] = []
        return "APPROVE E22"

    options = dict(
        confirm=confirm,
        notes_input=lambda _: "Owner-operated separate-account review; no institutional approval.",
    )
    if change == "cancel":
        cli.approve(*a.args, **options)
    else:
        with pytest.raises(DemoError):
            cli.approve(*a.args, **options)
    assert not a.p.posts and not (a.journal / "intent.json").exists()


@pytest.mark.parametrize("failure", ["none", "response", "receipt"])
def test_normal_approval_and_exact_interrupted_retries(approval, monkeypatch, capsys, failure):
    a = approval
    real = a.p.client.request
    persist = cli.persist

    def request(*args, **kwargs):
        response = real(*args, **kwargs)
        if args[0] == "POST" and failure == "response":
            raise DemoError("Simulated lost successful response")
        return response

    def save(path, value):
        if path.name == "receipt.json" and failure == "receipt":
            raise OSError("Simulated post-approval receipt failure")
        return persist(path, value)

    monkeypatch.setattr(a.p.client, "request", request)
    monkeypatch.setattr(cli, "persist", save)
    kwargs = dict(
        confirm=lambda _: "APPROVE E22",
        notes_input=lambda _: "  Owner-operated reviewer notes preserved verbatim.  ",
    )
    if failure == "none":
        cli.approve(*a.args, **kwargs)
    else:
        with pytest.raises(DemoError, match="may have committed"):
            cli.approve(*a.args, **kwargs)
    cli.approve(
        *a.args,
        confirm=lambda _: pytest.fail("No duplicate approval"),
        notes_input=lambda _: pytest.fail("Use durable selected notes"),
    )
    assert len(a.p.posts) == 1
    assert a.p.posts[0]["acknowledgements"] == a.selected["acknowledgements"]
    assert a.p.posts[0]["acknowledgements"] != a.p.payload["acknowledgements"]
    assert a.p.posts[0]["notes"] == "Owner-operated reviewer notes preserved verbatim."
    recovery = json.loads((a.journal / "receipt-recovery.json").read_text())
    assert "request_id" not in recovery and recovery["decision_id"] == a.sub["decisions"][0]["id"]
    if failure == "none":
        assert (
            json.loads((a.journal / "receipt.json").read_text())["request_id"]
            == a.p.client.last_request_id
        )
    assert "Owner-operated reviewer notes preserved verbatim" in capsys.readouterr().out
    a.selected["acknowledgements"]["0"] = "Reviewer changed candidate after the approval."
    persist(a.p.folder / "reviewer-proposal.json", a.selected)
    with pytest.raises(DemoError, match="intent/payload differs"):
        cli.approve(*a.args)
    assert len(a.p.posts) == 1


def test_clone_approve_requires_submission_validation_and_checksum_before_auth(monkeypatch):
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "muj_publication",
            "--naming-clone",
            "--action",
            "approve",
            "--draft",
            str(uuid4()),
            "--bundle",
            "/unused",
        ],
    )
    monkeypatch.setattr(
        original, "Client", lambda **kwargs: pytest.fail("Must reject before authentication")
    )
    with pytest.raises(SystemExit) as error:
        original.main()
    assert error.value.code == 2
