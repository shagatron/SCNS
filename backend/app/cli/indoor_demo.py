"""Local unpublished synthetic 3C setup, using normal authenticated HTTP APIs only."""

import fcntl
import getpass
import hashlib
import io
import json
import os
import re
import sys
import time
import warnings
from contextlib import contextmanager
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)
from uuid import UUID, uuid4, uuid5

from PIL import Image

ROOT = Path(__file__).resolve().parents[3] / "data/demo"
LABEL = "Synthetic 3C routing demo — UNPUBLISHED"
CALIBRATION = {
    "primary": {"start": {"x": 100, "y": 100}, "end": {"x": 300, "y": 100}, "distance_m": 10},
    "checks": [{"start": {"x": 100, "y": 100}, "end": {"x": 100, "y": 300}, "distance_m": 10}],
    "measured_on": "2026-10-01",
    "evidence": "Synthetic known10m per200 reference pixels; test assertion only.",
    "uncertainty_m": 0.05,
    "plan_quality": "uniform",
}


class DemoError(Exception):
    """Safe diagnostic without credentials or request bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DemoError("Unexpected redirect refused; credentials stay on the local API.")


class Client:
    def __init__(self, url="http://api:8000", origin="http://localhost:5173"):
        if url not in {"http://api:8000", "http://127.0.0.1:8000", "http://localhost:8000"}:
            raise DemoError("Only the documented local Compose API is supported.")
        self.url, self.origin, self.session = url, origin, None
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()), NoRedirect())

    def request(
        self, method, path, payload=None, *, headers=None, raw=None, binary=False, query=None
    ):
        if not path.startswith("/api/v1/") or ".." in path or "?" in path:
            raise DemoError("Unexpected API path.")
        suffix = ""
        if query is not None:
            if (
                method != "GET"
                or not re.fullmatch(r"/api/v1/admin/campuses/[0-9a-f-]{36}/audit", path)
                or not isinstance(query, dict)
                or set(query) != {"offset"}
                or type(query["offset"]) is not int
                or not 0 <= query["offset"] <= 100000
            ):
                raise DemoError("Only bounded read-only audit offsets are supported.")
            suffix = "?" + urlencode(query)
        h = {"Origin": self.origin, **(headers or {})}
        if self.session and method != "GET":
            h["X-CSRF-Token"] = self.session["csrf_token"]
        body = raw
        if payload is not None:
            h["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        try:
            with self.opener.open(
                Request(self.url + path + suffix, data=body, method=method, headers=h), timeout=60
            ) as response:
                self.last_request_id = response.headers.get("X-Request-ID")
                data = response.read()
                return data if binary else json.loads(data) if data else None
        except HTTPError as exc:
            # Validation bodies may echo inputs. Never print bodies or session objects.
            raise DemoError(
                f"API {method} failed (HTTP {exc.code}) at {path}; no bypass attempted."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise DemoError(
                "Local API unavailable/interrupted; rerun to reconcile progress."
            ) from None

    def login(self, username, password):
        self.session = self.request(
            "POST", "/api/v1/admin/login", {"username": username, "password": password}
        )
        return self.session

    def logout(self):
        if self.session:
            try:
                self.request("POST", "/api/v1/admin/logout")
            except DemoError:
                print("Helper logout unavailable; normal server expiry still applies.")
            self.session = None


def prompt_login(client, role):
    if not sys.stdin.isatty():
        raise DemoError("Secure terminal required. Use Compose run without -T or piping.")
    username = input(f"Existing {role} username: ").strip()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass(f"{role} password (hidden): ")
    except getpass.GetPassWarning:
        raise DemoError("Terminal cannot hide password input; refusing echoed fallback.") from None
    try:
        return client.login(username, password)
    finally:
        password = None


def fingerprint(root):
    files = [
        root / "floorplans/synthetic-ground.png",
        *sorted((root / "indoor-routing").glob("*.json")),
    ]
    return hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in files)).hexdigest()


def persist(path, state):
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(state, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def journal(directory, campus, owner, root=ROOT):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"{UUID(campus)}.json"
    with path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DemoError("Another demo setup is running for this campus.") from None
        if path.exists():
            try:
                state = json.loads(path.read_text())
                if state["owner"] != owner or state["fixtures"] != fingerprint(root):
                    raise DemoError(
                        "Journal owner/fixtures differ; existing demo retained for manual reconciliation."
                    )
                if state["campus"] != campus or state["format"] != "scns-local-3c-v1":
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                raise DemoError("Invalid journal retained untouched for manual recovery.") from None
        else:
            state = {
                "format": "scns-local-3c-v1",
                "label": LABEL,
                "campus": campus,
                "owner": owner,
                "run": str(uuid4()),
                "fixtures": fingerprint(root),
                "steps": {},
            }
            persist(path, state)
        yield path, state


def remap(value, namespace, bindings=None):
    if isinstance(value, dict):
        return {
            remap(k, namespace, bindings): remap(v, namespace, bindings) for k, v in value.items()
        }
    if isinstance(value, list):
        return [remap(v, namespace, bindings) for v in value]
    if isinstance(value, str):
        if bindings and value.startswith("$"):
            return bindings[value[1:]]
        try:
            UUID(value)
        except ValueError:
            return value
        return str(uuid5(UUID(namespace), value))
    return value


def changes(records):
    return [
        {"entity": e, "id": i, "data": row}
        for e, rows in records.items()
        for i, row in rows.items()
    ]


def subset(expected, actual):
    return isinstance(actual, dict) and all(actual.get(k) == v for k, v in expected.items())


def matching_records(expected, actual):
    present = [i in actual.get(e, {}) for e, rows in expected.items() for i in rows]
    if not any(present):
        return None
    if not all(present) or not all(
        subset(row, actual[e][i]) for e, rows in expected.items() for i, row in rows.items()
    ):
        raise DemoError("Demo records differ/are partial; user input retained, reconcile manually.")
    return True


class Setup:
    def __init__(self, owner, reviewer, path, state, reviewer_login, root=ROOT, wait_seconds=120):
        self.owner, self.reviewer, self.path, self.state = owner, reviewer, path, state
        self.reviewer_login, self.root, self.wait_seconds = reviewer_login, root, wait_seconds
        self.campus = f"/api/v1/admin/campuses/{state['campus']}"
        self.base = None

    def save(self):
        persist(self.path, self.state)

    def floors(self):
        return self.owner.request("GET", self.base + "/floors")

    def floor(self, identity):
        return next((f for f in self.floors()["floors"] if f["id"] == identity), None)

    def guard(self, name=None):
        data = self.floors()
        if data["status"] != "draft" or data["truncated"]:
            raise DemoError("Draft frozen/submitted or listing truncated; no edits performed.")
        version, before = data["edit_version"], self.state["edit_version"]
        if version != before and not (
            self.state.get("pending") == name and name and version == before + 1
        ):
            raise DemoError(
                "Draft changed outside recorded step; no overwrite, reconcile manually."
            )
        return version

    def write(self, method, path, payload=None, *, client=None, headers=None, raw=None):
        return (client or self.owner).request(
            method,
            self.base + path,
            payload,
            raw=raw,
            headers={"If-Match": f'"{self.state["edit_version"]}"', **(headers or {})},
        )

    def step(self, name, probe, action):
        if name in self.state["steps"]:
            return self.state["steps"][name]
        version = self.guard(name)
        result = probe()
        if result is None:
            if version != self.state["edit_version"]:
                raise DemoError(f"Cannot reconcile interrupted {name}; no automatic overwrite.")
            self.state["pending"] = name
            self.save()
            action()
            result = probe()
            if result is None:
                raise DemoError(f"Step {name} did not produce expected content; progress retained.")
        after = self.floors()["edit_version"]
        if after not in (self.state["edit_version"], self.state["edit_version"] + 1):
            raise DemoError("Concurrent change during setup; retained for reconciliation.")
        self.state["edit_version"] = after
        self.state["steps"][name] = result
        self.state.pop("pending", None)
        self.save()
        print(f"Completed: {name}", flush=True)
        return result

    def approve(self, floor):
        names = [f"{floor}/source approval", f"{floor}/calibration approval"]
        if all(n in self.state["steps"] for n in names):
            return
        if not self.reviewer.session:
            account = self.reviewer_login(self.reviewer)
            grant = next(
                (g for g in account["grants"] if g["campus_id"] == self.state["campus"]), None
            )
            if account["user_id"] == self.state["owner"]:
                raise DemoError("Independent reviewer must be a different existing account.")
            if not grant or "source_approve" not in grant["permissions"]:
                raise DemoError("Reviewer lacks live campus-scoped approval permission.")
        source = self.floor(floor)["layer"]["source_id"]
        print(
            f"Review {floor}: sanitized 600x400 plan, mask(480,320,100,60), two200px/10m lines, scale0.05m/px; invented test only."
        )
        self.step(
            names[0],
            lambda: True if self.floor(floor)["layer"]["approved"] else None,
            lambda: self.write("POST", f"/sources/{source}/approve", client=self.reviewer),
        )
        self.step(
            names[1],
            lambda: True if self.floor(floor)["frame"]["calibration"].get("reviewer") else None,
            lambda: self.write(
                "POST", f"/floors/{floor}/calibration/approve", client=self.reviewer
            ),
        )

    def setup_floor(self, key, building, ordering):
        identity = str(uuid5(UUID(self.state["run"]), key))
        payload = {
            "id": identity,
            "building_id": building,
            "code": f"D3C_{key}",
            "label": f"Synthetic 3C demo {key}",
            "ordering": ordering,
            "elevation_m": None,
            "visibility": "public",
        }

        def floor_probe():
            f = self.floor(identity)
            if f and not subset(payload, f):
                raise DemoError("Demo floor metadata differs; preserved without replacement.")
            return identity if f else None

        self.step(key + "/floor", floor_probe, lambda: self.write("POST", "/floors", payload))
        metadata = {
            "floor_id": identity,
            "key": f"{self.state['run']}_{key}",
            "filename": "synthetic-ground.png",
            "page": 1,
            "title": f"Synthetic 3C demo {key}",
            "rights": "synthetic",
            "provenance": "Invented two-floor topology test only, not institution source",
            "attribution": "Synthetic 3C test plan",
            "redactions": [{"x": 480, "y": 320, "width": 100, "height": 60}],
        }
        raw = (self.root / "floorplans/synthetic-ground.png").read_bytes()

        def upload_probe():
            jobs = self.owner.request("GET", self.base + "/floorplan-jobs")
            if jobs["total"] > 50:
                raise DemoError("Job listing exceeds helper bounds; reconcile manually.")
            job = next((j for j in jobs["items"] if j["options"]["key"] == metadata["key"]), None)
            if job and (
                job["options"] != metadata
                or job["original_checksum"] != hashlib.sha256(raw).hexdigest()
            ):
                raise DemoError("Upload content/options differ; retained without replacement.")
            return job["id"] if job else None

        job = self.step(
            key + "/upload",
            upload_probe,
            lambda: self.write(
                "POST",
                "/floorplan-jobs",
                raw=raw,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Floorplan-Metadata": quote(json.dumps(metadata)),
                },
            ),
        )
        deadline = time.monotonic() + self.wait_seconds
        while True:
            status = self.owner.request("GET", self.base + f"/floorplan-jobs/{job}")
            if status["state"] in {"ready", "applied"}:
                break
            if status["state"] in {"failed", "cancelled"} or time.monotonic() > deadline:
                raise DemoError(
                    f"Worker job {job}: {status['state']}. Inspect/retry normally, then rerun; no replacement."
                )
            time.sleep(1)
        png = self.owner.request("GET", self.base + f"/floorplan-jobs/{job}/preview", binary=True)
        with Image.open(io.BytesIO(png)) as image:
            image.load()
            if image.size != (600, 400) or image.convert("RGB").getpixel((500, 340)) != (
                255,
                255,
                255,
            ):
                raise DemoError("Actual worker PNG/mask differs from the documented fixture.")

        def applied():
            job_state = self.owner.request("GET", self.base + f"/floorplan-jobs/{job}")
            layer = self.floor(identity)["layer_id"]
            return (
                layer
                if layer and job_state["state"] == "applied" and layer == job_state["layer_id"]
                else None
            )

        self.step(
            key + "/apply",
            applied,
            lambda: self.write(
                "POST",
                f"/floorplan-jobs/{job}/apply",
                {"replace_layer_id": None, "reset_calibration": False},
            ),
        )

        def calibrated():
            value = self.floor(identity)["frame"]["calibration"]
            if value and not subset(CALIBRATION, value):
                raise DemoError("Calibration differs; retained without recalibration.")
            return True if value else None

        self.step(
            key + "/calibrate",
            calibrated,
            lambda: self.write("POST", f"/floors/{identity}/calibration", CALIBRATION),
        )
        self.approve(identity)
        frame = self.floor(identity)
        endpoint = f"/floors/{identity}/indoor"
        if not self.owner.request("GET", self.base + endpoint)["ready"]:
            raise DemoError("Current independent approvals are not live; inspect in admin.")
        records = remap(
            json.loads((self.root / f"indoor-routing/{key.lower()}.json").read_text())["records"],
            self.state["run"],
        )
        for row in records["rooms"].values():
            row["name"] = "Synthetic 3C demo: " + row["name"]
        body = {"layer_id": frame["layer_id"], "mode": "metric", "changes": changes(records)}
        self.step(
            key + "/trace",
            lambda: matching_records(records, self.owner.request("GET", self.base + endpoint)),
            lambda: (
                self.write("POST", endpoint + "/preview", body),
                self.write("PATCH", endpoint, body),
            ),
        )
        return identity, frame["layer_id"]

    def entrance(self, key, building, node, point):
        code = f"D3C_{self.state['run'][:8]}_{key}"
        fields = {
            "code": code,
            "name": f"Synthetic 3C demo {key} entrance",
            "kind": "entrance",
            "building_id": building,
            "visibility": "public",
            "point": point,
            "description": "Invented local demo entrance only; not surveyed campus data.",
        }

        def probe():
            for i, p in self.owner.request("GET", self.base + "/graph")["places"].items():
                if p["code"] == code:
                    if not subset(fields, p):
                        raise DemoError("Demo entrance differs; no existing place overwritten.")
                    return i
            return None

        place = self.step(
            key + "/place",
            probe,
            lambda: self.write("POST", "/catalog/places", {"entity": "places", "data": fields}),
        )
        identity = str(uuid5(UUID(self.state["run"]), key + "anchor"))
        records = {
            "anchors": {
                identity: {
                    "place_id": place,
                    "node_id": node,
                    "is_open": True,
                    "accessibility_status": "verified_step_free",
                    "accessibility_evidence": "Invented synthetic demo entrance 2026-10-01 only; no survey.",
                }
            }
        }
        self.step(
            key + "/anchor",
            lambda: matching_records(records, self.owner.request("GET", self.base + "/graph")),
            lambda: self.write("POST", "/graph", {"changes": changes(records)}),
        )
        return identity

    def run(self):
        dashboard = self.owner.request("GET", self.campus + "/dashboard")
        if not dashboard["is_demo"] or not {"catalog_edit", "draft_create", "review_submit"} <= set(
            dashboard["permissions"]
        ):
            raise DemoError(
                "Explicitly synthetic campus and existing owner/editor+submit permissions required."
            )
        release = dashboard["release"]["id"] if dashboard["release"] else None
        self.state.setdefault("published_release", release)
        if release != self.state["published_release"]:
            raise DemoError("Published baseline changed since setup began; existing demo retained.")
        if "draft" not in self.state:
            self.save()  # Persist retry key before possibly ambiguous POST.
            draft = self.owner.request(
                "POST", self.campus + "/drafts", headers={"Idempotency-Key": self.state["run"]}
            )
            # A replay after a lost response must not adopt intervening user edits.
            self.state.update(draft=draft["id"], draft_number=draft["version"], edit_version=1)
            self.save()
        self.base = self.campus + f"/drafts/{self.state['draft']}"
        print(f"{LABEL}: Draft{self.state['draft_number']} ({self.state['draft']})", flush=True)
        self.guard(self.state.get("pending"))
        buildings = [
            b
            for b in self.floors()["buildings"]
            if b["code"] == "ACA" and b["visibility"] == "public"
        ]
        if len(buildings) != 1:
            raise DemoError(
                "Published synthetic ACA building required; no existing buildings changed."
            )
        building = buildings[0]["id"]
        ground, ground_layer = self.setup_floor("Ground", building, 0)
        upper, upper_layer = self.setup_floor("Upper", building, 1)
        graph = self.owner.request("GET", self.base + "/graph")
        entrance = next(
            (
                i
                for i, p in graph["places"].items()
                if p["building_id"] == building and p["kind"] == "building"
            ),
            None,
        )
        candidates = [
            a
            for a in graph["anchors"].values()
            if a["place_id"] == entrance
            and a["is_open"]
            and graph["nodes"][a["node_id"]]["visibility"] == "public"
        ]
        east_nodes = [
            i
            for i, n in graph["nodes"].items()
            if n["label"] == "Central" and n["visibility"] == "public"
        ]
        if not candidates or len(east_nodes) != 1:
            raise DemoError(
                "Explicit ACA entrance/public Central node missing; no outdoor graph fabricated."
            )
        west_node = sorted(candidates, key=lambda a: a["node_id"])[0]["node_id"]
        west = self.entrance("West", building, west_node, graph["nodes"][west_node]["point"])
        east = self.entrance(
            "East", building, east_nodes[0], graph["nodes"][east_nodes[0]]["point"]
        )
        bindings = {
            "GROUND": ground,
            "UPPER": upper,
            "GROUND_LAYER": ground_layer,
            "UPPER_LAYER": upper_layer,
            "BUILDING": building,
            "ENTRANCE_A": west,
            "ENTRANCE_B": east,
        }
        records = remap(
            json.loads((self.root / "indoor-routing/connections.json").read_text())["records"],
            self.state["run"],
            bindings,
        )
        for c in records["connectors"].values():
            c["code"] = "D3C_" + c["code"]
            c["label"] = "Synthetic 3C demo: " + c["label"]
        body = {"changes": changes(records)}
        self.step(
            "connections and capability",
            lambda: matching_records(
                records, self.owner.request("GET", self.base + "/connections")
            ),
            lambda: (
                self.write("POST", "/connections/preview", body),
                self.write("PATCH", "/connections", body),
            ),
        )
        expected = remap(
            json.loads((self.root / "indoor-routing/expected.json").read_text()), self.state["run"]
        )
        gate = next((i for i, p in graph["places"].items() if p["code"] == "GATE"), None)
        if not gate:
            raise DemoError("Synthetic Main Gate absent; topology retained for manual review.")
        a, b, u, v = [expected[k] for k in ("ground_101", "ground_102", "upper_201", "upper_202")]
        pairs = [(a, b), (u, v), (a, u), (u, a), (gate, u), (u, gate)]
        routes = [
            {
                "source": s,
                "target": t,
                "profile": profile,
                "cost_mode": "metric",
                "expected_found": True,
                "reason": "Invented calibrated two-floor route evidence only; no surveyed campus claim",
            }
            for s, t in pairs
            for profile in ("shortest", "step_free")
        ]
        routes += [
            {
                "source": a,
                "target": expected["isolated"],
                "profile": p,
                "cost_mode": "metric",
                "expected_found": False,
                "reason": "Synthetic isolated room deliberately lacks a connected corridor; negative test only.",
            }
            for p in ("shortest", "step_free")
        ]

        for route in routes:
            route["maximum_distance_m"] = None

        def validation_probe():
            packet = self.owner.request("GET", self.base + "/review")
            return next(
                (
                    r
                    for r in packet["validations"]
                    if r["edit_version"] == packet["edit_version"]
                    and r["checksum"] == packet["checksum"]
                    and [
                        {k: v for k, v in case.items() if k not in {"actual", "passed", "error"}}
                        for case in r["evidence"]
                    ]
                    == routes
                ),
                None,
            )

        self.step(
            "route validation",
            validation_probe,
            lambda: self.write("POST", "/validations", {"routes": routes}),
        )
        result = self.state["steps"]["route validation"]
        latest = self.owner.request("GET", self.campus + "/dashboard")["release"]
        if (latest["id"] if latest else None) != release:
            raise DemoError(
                "Published pointer changed externally during setup; inspect before review."
            )
        self.guard()
        costs = [(a, b, "shortest", 18), (a, u, "shortest", 36), (a, u, "step_free", 57)]
        for start, end, profile, metres in costs:
            item = next(
                e
                for e in result["evidence"]
                if e["source"] == start and e["target"] == end and e["profile"] == profile
            )
            if not item["passed"] or item.get("actual", {}).get("distance_m") != metres:
                raise DemoError(
                    "Computed demo costs differ from documented fixtures; inspect retained route evidence."
                )
            print(f"Computed {profile}: {start} -> {end}: {metres}m (stored graph Dijkstra).")
        self.state["complete"] = result["report"]["errors"] == 0
        self.save()
        print(
            f"Validation {result['id']}: {result['report']['errors']} errors / {result['report']['warnings']} warnings; evidence in Review and releases."
        )
        print(
            "Expected synthetic: samefloor18m; shortest crossfloor36m/stairs; step-free57m/lift. Public release unchanged."
        )
        print(
            "Remaining: inspect diagnostics/rights/routes, acknowledge warnings, submit exact draft, independent review, explicit publication ONLY if separately desired."
        )
        if result["report"]["errors"]:
            raise DemoError(
                "Draft prepared but whole-draft validation has blocking diagnostics; inspect in admin. Nothing published."
            )
        return result


def main():
    owner, reviewer = Client(), Client()
    try:
        account = prompt_login(owner, "owner/editor")
        candidates = []
        for grant in account["grants"]:
            if "draft_create" in grant["permissions"]:
                data = owner.request(
                    "GET", f"/api/v1/admin/campuses/{grant['campus_id']}/dashboard"
                )
                if data["is_demo"]:
                    candidates.append(data)
        if not candidates:
            raise DemoError("No assigned synthetic campus; no accounts/campuses changed.")
        for i, campus in enumerate(candidates, 1):
            print(f"{i}: {campus['campus_name']} ({campus['campus_id']}) — synthetic")
        choice = 1 if len(candidates) == 1 else int(input("Synthetic campus number: "))
        if not 1 <= choice <= len(candidates):
            raise DemoError("Invalid campus selection.")
        campus = candidates[choice - 1]["campus_id"]
        with journal(Path("/app/storage/private/local-demo-3c"), campus, account["user_id"]) as (
            path,
            state,
        ):
            setup = Setup(
                owner, reviewer, path, state, lambda c: prompt_login(c, "independent reviewer")
            )
            try:
                setup.run()
            finally:
                print(
                    f"Private resume journal: {path}; completed steps:{len(state['steps'])}; draft:{state.get('draft', 'not created')}"
                )
        return 0
    except (DemoError, ValueError, OSError, KeyboardInterrupt) as exc:
        print(
            f"Stopped safely: {exc if isinstance(exc, DemoError) else 'Interrupted/invalid input.'} Rerun same command; no reset/reseed.",
            file=sys.stderr,
        )
        return 1
    finally:
        reviewer.logout()
        owner.logout()


if __name__ == "__main__":
    sys.exit(main())
