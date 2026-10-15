from copy import deepcopy
from uuid import uuid4

import pytest

from app.cli.indoor_demo import DemoError
from app.services.muj_setup import ROOT
from app.services.muj_update import apply_reviewed, correction, graph_records, plan


def state():
    _, rows = graph_records(ROOT)
    return {**rows, "revision_version": 5}


def completed(current, preview):
    result = deepcopy(current)
    for c in preview["changes"]:
        if c["data"] is None:
            del result[c["entity"]][c["id"]]
        else:
            result[c["entity"]][c["id"]] = c["data"]
    result["revision_version"] += 1
    return result


def test_exact_delta_has_explicit_deletes_and_preserves_unrelated_owner_work():
    current = state()
    current["nodes"][str(uuid4())] = {"owner_unrelated": True}
    preview = plan(current, uuid4())
    assert preview["counts"] == {"add": 20, "update": 0, "delete": 2}
    assert len(preview["before_records"]) == 22
    assert sum(c["entity"] == "anchors" for c in preview["changes"]) == 1
    updated = completed(current, preview)
    assert plan(updated, preview["draft_id"])["state"] == "already_applied"
    assert any(n.get("owner_unrelated") for n in updated["nodes"].values())


@pytest.mark.parametrize(
    "kind", ["edited_old_edge", "moved_endpoint", "new_id_collision", "manual_partial"]
)
def test_unexpected_changes_fail_without_mutating_input(kind):
    current = state()
    patch, baseline = correction()
    if kind == "edited_old_edge":
        c = next(c for c in patch["changes"] if c["data"] is None)
        current[c["entity"]][c["id"]]["evidence"] = "Legitimate owner survey: preserve"
    elif kind == "moved_endpoint":
        n = next(
            c["data"]["from_node_id"]
            for c in patch["changes"]
            if c["entity"] == "edges"
            and c["data"]
            and c["data"]["from_node_id"] in baseline["nodes"]
        )
        current["nodes"][n]["point"]["coordinates"][0] += 0.000001
    else:
        c = next(c for c in patch["changes"] if c["entity"] == "nodes" and c["data"])
        current["nodes"][c["id"]] = deepcopy(c["data"])
        if kind == "new_id_collision":
            current["nodes"][c["id"]]["label"] = "Owner-created different node"
    before = deepcopy(current)
    with pytest.raises(DemoError):
        plan(current, uuid4())
    assert current == before


def test_reviewed_version_and_payload_cannot_change_and_lost_response_retry_does_not_post():
    current = state()
    preview = plan(current, uuid4())

    class Client:
        posts = 0

        def request(self, method, path, *args, **kwargs):
            if method == "POST":
                self.posts += 1
                raise AssertionError("Must not post")
            return current

    client = Client()
    current["revision_version"] += 1
    with pytest.raises(DemoError, match="since preview"):
        apply_reviewed(client, preview)
    current["revision_version"] -= 1
    tampered = deepcopy(preview)
    tampered["changes"][0]["data"]["label"] = "Tampered"
    with pytest.raises(DemoError):
        apply_reviewed(client, tampered)
    current = completed(current, preview)
    assert apply_reviewed(client, preview)["state"] == "already_applied"
    assert client.posts == 0


def test_owner_edit_to_newly_anchored_destination_is_not_silently_reinterpreted():
    current = state()
    patch, _ = correction()
    anchor = next(c["data"] for c in patch["changes"] if c["entity"] == "anchors")
    current["places"][anchor["place_id"]]["point"]["coordinates"][0] += 0.0001
    with pytest.raises(DemoError, match="destination was edited"):
        plan(current, uuid4())
