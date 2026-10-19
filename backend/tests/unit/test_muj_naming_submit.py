"""Bounded E22 submit guards; actual API history is covered in integration."""

import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cli import muj_naming_review as cli
from app.cli.indoor_demo import DemoError


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    user, draft, validation = map(str, (uuid4(), uuid4(), uuid4()))
    sha = "a" * 64
    report = {key: {} for key in cli.SUBMIT_PROOF}
    report.update(
        scope_type="e22-naming-clone",
        campus_id=str(cli.CAMPUS_ID),
        draft_id=draft,
        prepared_by=user,
        version=3,
        status="draft",
        checksum=sha,
        validation_id=validation,
        blockers=[],
        existing_submissions=[],
        proposed_reasons={str(i): "Previously reviewed substantive reason." for i in range(145)},
    )
    folder = tmp_path / "private/muj-naming-review" / draft / user / f"v3-{sha}-{validation}"
    folder.mkdir(parents=True)
    cli.persist(folder / "report.json", report)
    payload = dict(validation_id=validation, acknowledgements=deepcopy(report["proposed_reasons"]))
    cli.persist(folder / "proposal.json", payload)
    current = deepcopy(report)
    posts = []

    class Client:
        session = {"user_id": user}
        last_request_id = "actual-response-request-id"

        def request(self, method, path, body, *, headers):
            assert method == "POST" and path.endswith(f"/{draft}/submissions")
            assert headers == {"If-Match": '"3"'}
            posts.append(deepcopy(body))
            current.update(
                version=4,
                status="review",
                existing_submissions=[
                    dict(
                        id=str(uuid4()),
                        status="submitted",
                        submitter_id=user,
                        validation_id=validation,
                        checksum=sha,
                        edit_version=4,
                        acknowledgements=deepcopy(body["acknowledgements"]),
                    )
                ],
            )
            return current["existing_submissions"][0]

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(storage_root=tmp_path))
    monkeypatch.setattr(cli, "collect", lambda *args: deepcopy(current))
    c = Client()
    return SimpleNamespace(
        client=c,
        folder=folder,
        report=report,
        payload=payload,
        current=current,
        posts=posts,
        args=(c, draft, validation, folder, 3, sha),
    )


@pytest.mark.parametrize(
    "change", ["missing", "extra", "empty", "short", "wrong-validation", "duplicate-key"]
)
def test_invalid_payload_is_preserved_without_confirmation_or_write(prepared, change):
    p = prepared
    if change == "missing":
        p.payload["acknowledgements"].pop("0")
    elif change == "extra":
        p.payload["acknowledgements"]["stale"] = "Preserved stale owner reason."
    elif change == "empty":
        p.payload["acknowledgements"]["0"] = "   "
    elif change == "short":
        p.payload["acknowledgements"]["0"] = "yes"
    elif change == "wrong-validation":
        p.payload["validation_id"] = str(uuid4())
    cli.persist(p.folder / "proposal.json", p.payload)
    if change == "duplicate-key":
        (p.folder / "proposal.json").write_text('{"validation_id":"a","validation_id":"b"}')
    before = (p.folder / "proposal.json").read_bytes()
    with pytest.raises(DemoError):
        cli.submit(*p.args, confirm=lambda _: pytest.fail("Must refuse before prompt"))
    assert not p.posts and (p.folder / "proposal.json").read_bytes() == before


@pytest.mark.parametrize("change", ["checksum", "version", "owner", "proof", "blocked", "history"])
def test_stale_or_foreign_evidence_stops(prepared, change):
    p = prepared
    if change == "checksum":
        p.current["checksum"] = "b" * 64
    elif change == "version":
        p.current["version"] = 4
    elif change == "owner":
        p.client.session = {"user_id": str(uuid4())}
    elif change == "proof":
        p.current["sources"] = {"changed": {}}
    elif change == "blocked":
        p.current["blockers"] = ["Unexplained finding"]
    elif change == "history":
        p.current["existing_submissions"] = [dict(status="rejected")]
    with pytest.raises(DemoError):
        cli.submit(*p.args, confirm=lambda _: pytest.fail("Must refuse before prompt"))
    assert not p.posts


@pytest.mark.parametrize("change", ["cancel", "payload", "report", "proof", "version"])
def test_confirmation_and_post_confirmation_races_preserve_input(prepared, change):
    p = prepared

    def confirm(_):
        if change == "cancel":
            return "SUBMIT"
        if change == "payload":
            p.payload["acknowledgements"]["0"] = "Owner text changed while reading; retain me."
            cli.persist(p.folder / "proposal.json", p.payload)
        elif change == "report":
            (p.folder / "report.json").write_text("{}")
        elif change == "proof":
            p.current["original_imports"] = ["changed"]
        elif change == "version":
            p.current["version"] = 4
        return "SUBMIT E22"

    if change == "cancel":
        cli.submit(*p.args, confirm=confirm)
    else:
        with pytest.raises(DemoError):
            cli.submit(*p.args, confirm=confirm)
    assert not p.posts and not (p.folder / "intent-submit.json").exists()
    if change == "payload":
        assert json.loads((p.folder / "proposal.json").read_text()) == p.payload


def test_success_exact_payload_and_retry_receipts(prepared, capsys):
    p = prepared
    p.payload["acknowledgements"]["0"] = "  Individually edited owner reason, including spacing.  "
    cli.persist(p.folder / "proposal.json", p.payload)
    cli.submit(*p.args, confirm=lambda _: "SUBMIT E22")
    assert p.posts == [p.payload]
    receipt = json.loads((p.folder / "receipt-submit.json").read_text())
    assert receipt["request_id"] == p.client.last_request_id
    cli.submit(*p.args, confirm=lambda _: pytest.fail("Already applied: no prompt/write"))
    recovered = json.loads((p.folder / "receipt-submit-recovery.json").read_text())
    assert "request_id" not in recovered and len(p.posts) == 1
    assert receipt == json.loads((p.folder / "receipt-submit.json").read_text())
    assert "Individually edited owner reason" in capsys.readouterr().out
    p.payload["acknowledgements"]["0"] = "Changed reason after the server submission."
    cli.persist(p.folder / "proposal.json", p.payload)
    with pytest.raises(DemoError, match="intent differs"):
        cli.submit(*p.args)
    assert len(p.posts) == 1


def test_server_reconciliation_does_not_depend_on_local_intent_or_invent_audit(prepared):
    p = prepared
    cli.submit(*p.args, confirm=lambda _: "SUBMIT E22")
    (p.folder / "intent-submit.json").unlink()  # Isolated fixture simulates lost local journal.
    cli.submit(*p.args, confirm=lambda _: pytest.fail("No repeat submission"))
    recovered = json.loads((p.folder / "receipt-submit-recovery.json").read_text())
    assert len(p.posts) == 1 and "request_id" not in recovered
    assert recovered["submission_id"] == p.current["existing_submissions"][0]["id"]


@pytest.mark.parametrize(
    "omit", ["--bundle", "--validation", "--expected-version", "--expected-checksum"]
)
def test_clone_submit_requires_explicit_bindings_before_authentication(monkeypatch, omit):
    import sys

    from app.cli import muj_publication as original

    flags = {
        "--bundle": "/unused",
        "--validation": str(uuid4()),
        "--expected-version": "3",
        "--expected-checksum": "a" * 64,
    }
    args = ["muj_publication", "--naming-clone", "--action", "submit", "--draft", str(uuid4())]
    for key, value in flags.items():
        if key != omit:
            args.extend([key, value])
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(
        original, "Client", lambda **kwargs: pytest.fail("Must reject before authentication")
    )
    with pytest.raises(SystemExit) as error:
        original.main()
    assert error.value.code == 2
