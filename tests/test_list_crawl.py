import json
from pathlib import Path

import pytest
from tools.lists import Run, split_partition, publish, atomic_json
from awesome.catalogue import digest
from awesome.lists import FORMAT
from tests.test_lists import build_index


def repo(n, stars=100):
    return {"id": n, "node_id": f"node{n}", "full_name": f"owner/list{n}", "html_url": f"https://github.com/owner/list{n}",
            "description": "A curated list", "private": False, "stargazers_count": stars, "forks_count": 0}


def part(**values):
    return {"base": "awesome is:public fork:true", "start": "2020-01-01", "end": "2020-01-02", "low": 100, "high": None, **values}


def test_date_and_star_partitions_nonoverlap():
    a, b = split_partition(part(), 200)
    assert a["end"] == "2020-01-01" and b["start"] == "2020-01-02"
    a, b = split_partition(part(end="2020-01-01"), 200)
    assert a["high"] + 1 == b["low"]
    assert split_partition(part(end="2020-01-01"), 100) is None


class Pages:
    def __init__(self): self.calls = []
    def search(self, query, page):
        self.calls.append((query, page))
        return {"total_count": 101, "incomplete_results": False,
                "items": [repo(n) for n in (range(100) if page == 1 else [100])]}


def test_page_interruption_resume_and_dedup(tmp_path):
    api = Pages(); run = Run("test", tmp_path, api)
    run.state["queue"] = [part(), {**part(), "base": "topic:awesome"}]; run.save()
    with pytest.raises(InterruptedError): run.discover(interrupt_after=1)
    assert len(api.calls) == 1
    resumed = Run("test", tmp_path, api); resumed.discover()
    assert len(api.calls) == 4
    assert len(resumed.state["candidates"]) == 101
    assert all(p["status"] == "reconciled" for p in resumed.state["partitions"])
    before = len(api.calls); Run("test", tmp_path, api).discover(); assert len(api.calls) == before


def test_unsplittable_incomplete_retains_observed_candidates(tmp_path):
    class Saturated:
        def search(self, query, page): return {"total_count": 1001, "incomplete_results": False, "items": [repo(1)]}
    run = Run("test", tmp_path, Saturated()); run.state["queue"] = [part(end="2020-01-01")]; run.save(); run.discover()
    assert run.state["partitions"][0]["status"] == "unresolved"
    assert "1" in run.state["candidates"]


def test_changing_total_not_claimed_complete(tmp_path):
    class Changing(Pages):
        def search(self, query, page):
            response = super().search(query, page)
            if page == 2: response["total_count"] = 102
            return response
    run = Run("test", tmp_path, Changing()); run.state["queue"] = [part()]; run.save(); run.discover()
    assert run.state["partitions"][0]["status"] == "unresolved"


def test_exact_thousand_fetches_all_ten_pages(tmp_path):
    class Thousand:
        def __init__(self): self.calls = []
        def search(self, query, page):
            self.calls.append(page)
            return {"total_count": 1000, "incomplete_results": False,
                    "items": [repo(n) for n in range((page-1)*100, page*100)]}
    api = Thousand(); run = Run("test", tmp_path, api)
    run.state["queue"] = [part()]; run.save(); run.discover()
    assert api.calls == list(range(1, 11))
    assert len(run.state["candidates"]) == 1000
    assert run.state["partitions"][0]["status"] == "reconciled"


def test_empty_second_page_remains_unresolved(tmp_path):
    class Empty(Pages):
        def search(self, query, page):
            result = super().search(query, page)
            if page == 2: result["items"] = []
            return result
    run = Run("test", tmp_path, Empty()); run.state["queue"] = [part()]; run.save(); run.discover()
    assert run.state["partitions"][0]["status"] == "unresolved"


def test_incomplete_unsplittable_response_explicit(tmp_path):
    class Incomplete:
        def search(self, query, page): return {"total_count": 1, "incomplete_results": True, "items": [repo(1)]}
    run = Run("test", tmp_path, Incomplete()); run.state["queue"] = [part(end="2020-01-01")]; run.save(); run.discover()
    assert run.state["partitions"][0]["status"] == "unresolved"


def test_successful_content_uses_frozen_commit(tmp_path):
    from tests.test_lists import MD, meta
    class Response:
        def graphql(self, query):
            assert ('a'*40 + ':README.md') in query and 'HEAD:' not in query
            return {"data": {"r0": {"id": "node1", "isPrivate": False,
                    "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}}}
    run = Run("test", tmp_path, Response()); source = meta(id="1", node_id="node1")
    run.state["candidates"]["1"] = source; run.content([source])
    item = run.state["completed"]["1"]
    assert item["state"] == "eligible" and item["entry_count"] == 5
    assert (tmp_path / 'data/staging' / item['detail']).exists()


def test_missing_shard_rejects_publication(tmp_path):
    index, _ = build_index(); atomic_json(tmp_path / "data/staging/list-index.json", index)
    with pytest.raises(FileNotFoundError): publish(index["digest"], tmp_path)
    assert not (tmp_path / "data/list-index.json").exists()


def test_tampered_checkpoint_rejected(tmp_path):
    run = Run("test", tmp_path, Pages()); state = json.loads(run.path.read_text()); state["threshold"] = 1
    run.path.write_text(json.dumps(state))
    with pytest.raises(ValueError): Run("test", tmp_path, Pages())


def test_graphql_partial_metadata_does_not_complete_batch(tmp_path):
    class Partial:
        def graphql(self, query): return {"data": {"r0": None}, "errors": [{"path": ["r0"], "message": "unavailable"}]}
    run = Run("test", tmp_path, Partial())
    run.metadata([{"id": "1", "name": "owner/list1"}])
    assert not run.state["metadata"] and "1" in run.state["errors"]


@pytest.mark.parametrize("private,node", [(True, "node1"), (False, "different-node")])
def test_metadata_private_and_reused_name_rejected(tmp_path, private, node):
    class Response:
        def graphql(self, query):
            return {"data": {"r0": {"id": node, "isPrivate": private,
                      "description": "PRIVATE SECRET", "defaultBranchRef": {"name": "main", "target": {"oid": "a"*40}}}}}
    run = Run("test", tmp_path, Response())
    source = {"id": "1", "node_id": "node1", "name": "owner/list1", "url": "https://github.com/owner/list1", "public": True,
              "description": "Previously public description", "stars": 100, "observed_at": "2026-09-03T00:00:00Z"}
    run.metadata([source])
    assert not run.state["metadata"]
    assert "PRIVATE SECRET" not in json.dumps(run.state)
    if private: assert run.state["completed"]["1"]["state"] == "excluded"
    else: assert "identity" in run.state["errors"]["1"]


@pytest.mark.parametrize("private,node", [(True, "node1"), (False, "different-node")])
def test_content_identity_and_privacy_rechecked(tmp_path, private, node):
    class Response:
        def graphql(self, query):
            assert "id isPrivate" in query
            return {"data": {"r0": {"id": node, "isPrivate": private, "f0": {"text": "PRIVATE SECRET", "byteSize": 14, "isBinary": False}}}}
    run = Run("test", tmp_path, Response())
    source = {"id": "1", "node_id": "node1", "name": "owner/list1", "url": "https://github.com/owner/list1", "public": True,
              "description": "Previously public", "stars": 100, "observed_at": "2026-09-03T00:00:00Z", "revision": "a"*40}
    run.state["candidates"]["1"] = source
    run.content([source])
    assert "PRIVATE SECRET" not in json.dumps(run.state)
    assert not (tmp_path / "data/raw").exists()


def test_dependency_fingerprint_invalidates_resume(tmp_path, monkeypatch):
    import tools.lists as crawler
    Run("test", tmp_path, Pages())
    old = crawler.engine()
    monkeypatch.setattr(crawler, "version", lambda _: "changed-parser")
    assert crawler.engine() != old
    with pytest.raises(ValueError): Run("test", tmp_path, Pages())


def test_publish_index_last_and_stale_shard(tmp_path):
    index, detail = build_index(); staging = tmp_path / "data/staging"
    atomic_json(staging / "list-index.json", index); atomic_json(staging / index["lists"][0]["detail"], detail)
    sentinel = {"last_good": True}; atomic_json(tmp_path / "data/list-index.json", sentinel)
    with pytest.raises(ValueError): publish("0" * 64, tmp_path)
    with pytest.raises(InterruptedError): publish(index["digest"], tmp_path, interrupt_after=1)
    assert json.loads((tmp_path / "data/list-index.json").read_text()) == sentinel
    publish(index["digest"], tmp_path)
    assert json.loads((tmp_path / "data/list-index.json").read_text())["digest"] == index["digest"]
    publish(index["digest"], tmp_path)
    detail["entry_count"] = 999; atomic_json(staging / index["lists"][0]["detail"], detail)
    with pytest.raises(ValueError): publish(index["digest"], tmp_path)


def test_parser_rejection_is_isolated_to_repository(tmp_path, monkeypatch):
    import tools.lists as crawler
    from tests.test_lists import MD, meta
    class Response:
        def graphql(self, query):
            return {"data": {f"r{i}": {"id": f"node{i}", "isPrivate": False,
                    "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}
                    for i in (1, 0)}}
    original = crawler.parse_readme
    def selective(text, name, revision, path):
        if name == "owner/broken": raise ValueError("Fixture parser rejection")
        return original(text, name, revision, path)
    monkeypatch.setattr(crawler, "parse_readme", selective)
    run = Run("test", tmp_path, Response())
    sources = [meta(id=str(i), node_id=f"node{i}", name=f"owner/{name}") for i, name in enumerate(("broken", "good"))]
    run.state["candidates"] = {m["id"]: m for m in sources}
    run.content(sources)
    assert "0" in run.state["errors"] and "1" in run.state["completed"]
    assert Run("test", tmp_path, Response()).state["errors"] == run.state["errors"]


@pytest.mark.parametrize("tamper", [False, True])
@pytest.mark.parametrize("same_length", [False, True])
def test_text_rendition_mismatch_fetches_exact_blob(tmp_path, tamper, same_length):
    import base64
    import hashlib
    from tests.test_lists import MD, meta
    raw = MD.replace("Tool", "Good").encode() if same_length else b"\xef\xbb\xbf" + MD.replace("\n", "\r\n").encode()
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    class Response:
        def graphql(self, query):
            return {"data": {"r0": {"id": "node1", "isPrivate": False,
                "f0": {"text": MD, "byteSize": len(raw), "isBinary": False, "oid": oid}}}}
        def request(self, endpoint):
            assert endpoint.endswith("/git/blobs/" + oid)
            return {"encoding": "base64", "content": base64.b64encode(raw if not tamper else raw[:-1]).decode()}
    run = Run("test", tmp_path, Response()); source = meta(id="1", node_id="node1")
    run.state["candidates"]["1"] = source; run.content([source])
    if tamper:
        assert "1" in run.state["errors"] and not run.state["completed"]
    else:
        assert run.state["completed"]["1"]["entry_count"] == 5
        assert run.state["completed"]["1"]["readme_sha256"] == hashlib.sha256(raw).hexdigest()


def test_replay_verifies_source_and_reparses_raw(tmp_path, monkeypatch):
    import tools.lists as crawler
    from tests.test_lists import MD, meta
    class Response:
        def graphql(self, query):
            return {"data": {"r0": {"id": "node1", "isPrivate": False,
                "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}}}
    old = Run("old", tmp_path, Response()); source = meta(id="1", node_id="node1")
    old.state.update(queue=[], discovery_completed_at=source["observed_at"], candidates={"1": source}, metadata={"1": source})
    old.content([source]); before = old.path.read_bytes()
    checksum = json.loads(before)["checkpoint_digest"]
    monkeypatch.setattr(crawler, "engine", lambda: "new-reviewed-engine")
    with pytest.raises(ValueError): Run("old", tmp_path)
    new = Run("new", tmp_path)
    with pytest.raises(ValueError): new.replay("old", "0"*64)
    new.replay("old", checksum)
    assert new.state["completed"]["1"]["entry_count"] == 5
    assert new.state["replay"]["raw_inputs_reparsed"] == 1
    assert new.state["engine"] == "new-reviewed-engine" and old.path.read_bytes() == before
    with pytest.raises(ValueError): new.replay("old", checksum)
    raw = tmp_path / "data/raw/lists/1" / source["revision"] / "README.md"
    raw.write_text("tampered")
    with pytest.raises(ValueError): Run("tampered", tmp_path).replay("old", checksum)


def test_profile_history_is_pinned_bounded_public_and_resumable(tmp_path):
    from tests.test_lists import MD, meta
    class ProfileResponse:
        def __init__(self): self.calls = 0
        def graphql(self, query):
            self.calls += 1
            if "history(first:100" not in query:
                return {"data": {"r0": {"id": "node1", "isPrivate": False,
                    "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}}}
            assert "history(first:100,path:\"README.md\")" in query and "email" not in query.casefold()
            return {"data": {"r0": {"id": "node1", "isPrivate": False,
                "root": {"history": {"totalCount": 121, "pageInfo": {"hasNextPage": True}, "nodes": [
                    {"committedDate": "2026-09-02T00:00:00Z", "author": {"user": {"login": "alice", "url": "https://github.com/alice"}}},
                    {"committedDate": "2026-08-01T00:00:00Z", "author": {"user": None}},
                    {"committedDate": "2026-07-01T00:00:00Z", "author": {"user": {"login": "alice", "url": "https://github.com/alice"}}}]}},
                "c0": {"oid": "b"*40}, "c1": None}}}
    api = ProfileResponse(); run = Run("test", tmp_path, api); source = meta(id="1", node_id="node1")
    run.state["candidates"]["1"] = source; run.content([source]); run.profiles(interrupt_after=None, batch_size=1)
    item = run.state["completed"]["1"]
    assert item["contributors_count"] == 1 and item["content_updated_at"] == "2026-09-02T00:00:00Z"
    assert item["contributor_observation"]["observed_commits"] == 3 and item["contributor_observation"]["has_more"] is True
    assert item["contributing_url"].endswith("/CONTRIBUTING.md")
    assert api.calls == 2  # content then profile
    Run("test", tmp_path, api).profiles(batch_size=1)
    assert api.calls == 2
    assert not (run.directory / "profile-checkpoint.json").exists()


def test_partial_profile_alias_stays_retryable(tmp_path):
    from tests.test_lists import MD, meta
    class Response:
        def graphql(self, query):
            if "history(first:100" in query: return {"data": {"r0": None}, "errors": [{"path": ["r0"]}]}
            return {"data": {"r0": {"id": "node1", "isPrivate": False,
                "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}}}
    run = Run("test", tmp_path, Response()); source = meta(id="1", node_id="node1")
    run.state["candidates"]["1"] = source; run.content([source]); run.profiles(batch_size=1)
    assert "1" not in run.state["profile_observations"] and "1" in run.state["profile_errors"]
    assert run.state["completed"]["1"]["contributors_count"] is None


def test_staged_index_uses_current_model_contract(tmp_path):
    run = Run("test", tmp_path, Pages()); run.state.update(queue=[], candidates={}, discovery_completed_at="2026-09-03T00:00:00Z")
    index = run.stage()
    assert index["format_version"] == FORMAT


def test_profile_interruption_uses_small_digest_bound_sidecar(tmp_path):
    from tests.test_lists import MD, meta
    class Response:
        def graphql(self, query):
            if "history(first:100" not in query:
                return {"data": {"r0": {"id": "node1", "isPrivate": False, "f0": {"text": MD, "byteSize": len(MD.encode()), "isBinary": False}}}}
            return {"data": {"r0": {"id": "node1", "isPrivate": False, "root": {"history": {"totalCount": 1, "pageInfo": {"hasNextPage": False}, "nodes": [{"committedDate": "2026-09-02T00:00:00Z", "author": {"user": None}}]}}, "c0": None, "c1": None}}}
    run = Run("test", tmp_path, Response()); source = meta(id="1", node_id="node1")
    run.state["candidates"]["1"] = source; run.content([source])
    with pytest.raises(InterruptedError): run.profiles(interrupt_after=1, batch_size=1)
    sidecar = json.loads((run.directory / "profile-checkpoint.json").read_text())
    assert sidecar["digest"] == digest({k: v for k, v in sidecar.items() if k != "digest"})
    assert len(sidecar["observations"]) == 1 and (run.directory / "profile-checkpoint.json").stat().st_size < 10_000
    Run("test", tmp_path, Response()).profiles(batch_size=1)
    assert not (run.directory / "profile-checkpoint.json").exists()
