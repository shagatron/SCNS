from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.schemas.closures import ClosureCreate, ClosureDecision
from app.services.closures import apply, target


def test_explicit_verification_and_aware_dates():
    with pytest.raises(ValidationError):
        ClosureDecision(key="retry-key", evidence="Synthetic verification", confirmed=False)
    with pytest.raises(ValidationError):
        ClosureCreate(
            key="retry-key",
            target_kind="connector",
            target_id=uuid4(),
            reason="Synthetic outage",
            starts_at="2026-10-08T00:00:00",
        )


def test_future_unknown_eta_and_unresolved_are_conservative_without_mutation():
    identity = str(uuid4())
    data = {
        "nodes": {"a": {"label": "A"}, "b": {"label": "B"}},
        "edges": {
            identity: {
                "id": identity,
                "physical_path_id": identity,
                "from_node_id": "a",
                "to_node_id": "b",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                "is_open": True,
            }
        },
    }
    now = datetime.now(UTC)
    entry = SimpleNamespace(
        target_kind="outdoor_edge",
        target_id=identity,
        target_checksum=target(data, "outdoor_edge", identity)["checksum"],
        starts_at=now + timedelta(hours=2),
        state="closed",
    )
    assert apply(data, [entry], now + timedelta(hours=1))["edges"][identity]["is_open"]
    assert not apply(data, [entry], None)["edges"][identity]["is_open"]
    assert data["edges"][identity]["is_open"]
    entry.state = "unresolved"
    with pytest.raises(DomainError, match="target review"):
        apply(data, [entry], None)
    with pytest.raises(DomainError, match="target review"):
        apply(data, [entry], now + timedelta(hours=1))
    entry.state = "reopened"
    assert apply(data, [entry], None)["edges"][identity]["is_open"]
