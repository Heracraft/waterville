"""eval/run.py and eval/questions.yaml: question set integrity, citation matching, SSE reading, scoring and a full run against the app in FAKE_AZURE mode."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import PASSWORD
from ecode.state import citation_of

REPO = Path(__file__).resolve().parents[1]


def _load_run():
    spec = importlib.util.spec_from_file_location("eval_run", REPO / "eval" / "run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_run"] = mod  # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    return mod


run = _load_run()


# ---------------------------------------------------------------- question set


def test_question_set_shape():
    qs = run.load_questions(REPO / "eval" / "questions.yaml")
    assert len(qs) == 30
    assert len({q.id for q in qs}) == 30
    for q in qs:
        assert q.question.endswith("?"), q.id
        assert q.expect and all(q.expect), q.id
        assert re.fullmatch(r"2\.[1-8]", q.step), q.id
    # Every workflow step in section 2 is covered.
    assert {q.step for q in qs} >= {"2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7"}


def _known_citations() -> set[str]:
    known: set[str] = set()
    chunks = REPO / "output" / "chunks.jsonl"
    with chunks.open(encoding="utf-8") as f:
        for line in f:
            if c := json.loads(line).get("citation"):
                known.add(c)
    sources = tomllib.loads((REPO / "ecode" / "state_sources.toml").read_text(encoding="utf-8"))
    for s in sources.get("source", []):
        if s.get("tier") == "superseded":
            continue
        if c := s.get("citation"):
            known.add(c)
        # Entries without a citation are cited by ecode.state.citation_of(title)
        # ("30-A M.R.S. § 4452. Enforcement ..." -> "30-A M.R.S. § 4452").
        title = s.get("title", "")
        known.add(citation_of(title))
        if m := re.match(r"(\d+(?:-A)? M\.R\.S\.) §§ (\d+)-(\d+)", title):
            known.update(f"{m[1]} § {n}" for n in range(int(m[2]), int(m[3]) + 1))
    notes = tomllib.loads((REPO / "ecode" / "staff_notes.toml").read_text(encoding="utf-8"))
    known.update(f"Staff note: {n['title']}" for n in notes.get("note", []))
    return known


def test_expected_citations_exist_in_the_corpus():
    known = _known_citations()
    qs = run.load_questions(REPO / "eval" / "questions.yaml")
    missing = [(q.id, alt) for q in qs for alts in q.expect for alt in alts if alt not in known]
    assert not missing, missing


def test_fact_patterns_compile_and_are_case_insensitive():
    for q in run.load_questions(REPO / "eval" / "questions.yaml"):
        for f in q.facts:
            re.compile(f, re.I)


def test_load_rejects_unknown_fields(tmp_path):
    p = tmp_path / "q.yaml"
    p.write_text("questions:\n  - id: a\n    question: x?\n    expect: ['§ 1-1']\n    expected: oops\n")
    with pytest.raises(ValueError, match="unknown fields"):
        run.load_questions(p)
    p.write_text("questions:\n  - id: a\n    question: x?\n    expect: []\n")
    with pytest.raises(ValueError, match="no expected"):
        run.load_questions(p)


# ---------------------------------------------------------------- matching


@pytest.mark.parametrize(
    ("expected", "actual", "ok"),
    [
        ("§ 205-7", "§ 205-7", True),
        ("§ 205-7", "§ 205-7A", True),
        ("§ 205-7", "§205-7", True),
        ("§ 205-7", "§ 205-70", False),
        ("§ 275-6.2", "§ 275-6.21", False),
        ("§ 275-6.2", "§ 275-6.2E(1)", True),
        ("§ 275-4.2", "§ 275-4.27", False),
        ("30-A M.R.S. § 4452", "30-A M.R.S. § 4452", True),
        ("30-A M.R.S. § 4452", "30-A M.R.S. § 4452(3)", True),
        ("30-A M.R.S. § 3754", "30-A M.R.S. § 3754-A", False),
        ("08-003 CMR ch. 2", "08-003 CMR ch. 2", True),
        ("08-003 CMR ch. 2", "08-003 CMR ch. 20", False),
        ("M.R. Civ. P. 80K", "M.R. Civ. P. 80K", True),
        ("M.R. Civ. P. 80K", "M.R. Civ. P. 80B", False),
        ("Court Rule 80K Manual (2017)", "Court Rule 80K Manual (2017)", True),
        ("§ 205-7", None, False),
    ],
)
def test_cite_matches(expected, actual, ok):
    assert run.cite_matches(expected, actual) is ok


def test_mentioned():
    text = "**§ 205-7A; 30-A M.R.S. § 4452(3)(B)** The owner gets notice under Sec. 127-3B."
    assert run.mentioned("§ 205-7", text)
    assert run.mentioned("30-A M.R.S. § 4452", text)
    assert run.mentioned("§ 127-3", text)
    assert not run.mentioned("§ 205-70", text)
    assert not run.mentioned("§ 205-8", text)
    assert not run.mentioned("§ 275-6.2", "see § 275-6.21")
    assert run.mentioned("§ 275-6.2", "see § 275-6.2F.")


# ---------------------------------------------------------------- SSE and scoring


def test_read_sse():
    raw = 'event: meta\ndata: {"mode": "staff"}\n\nevent: delta\ndata: {"text": "a"}\n\nevent: done\ndata: {}\n\n'
    assert list(run.read_sse(raw.split("\n"))) == [("meta", {"mode": "staff"}), ("delta", {"text": "a"}), ("done", {})]
    # A final event without a blank line, and multi-line data.
    assert list(run.read_sse(["event: x", "data: 1", "data: 2"])) == [("x", "1\n2")]


def _result(answer, sources, expect, facts=()):
    r = run.Result("q", "2.5", "Q?", [[a.strip() for a in e.split("|")] for e in expect], list(facts), answer=answer, sources=sources)
    r.cited = sorted({int(n) for n in run.CITE_RE.findall(answer)})
    return run.score(r)


def test_score_cited_named_and_missing():
    sources = [{"n": 1, "citation": "§ 205-7"}, {"n": 2, "citation": "§ 205-8"}, {"n": 3, "citation": "30-A M.R.S. § 4452"}]
    r = _result("Notice goes to the owner and mortgagee [1]. Penalty $100 per day.", sources, ["§ 205-7", "§ 205-8 | § 999-1"], [r"\$100", "mortgagee"])
    assert [h["hit"] for h in r.hits] == [True, False]
    assert r.hits[1]["retrieved"] and not r.hits[1]["cited"]
    assert r.facts_found == [True, True]
    assert not r.passed

    # Named in the text and retrieved counts as a hit even without [n].
    r = _result("Under § 205-8 the penalty is $100 [1].", sources, ["§ 205-7", "§ 205-8"])
    assert all(h["hit"] for h in r.hits) and r.passed

    # Named but never retrieved does not count.
    r = _result("See § 210-10 [1].", sources, ["§ 210-10"])
    assert not r.hits[0]["hit"]

    # An error fails the question whatever it cites.
    r = _result("[1]", sources, ["§ 205-7"])
    r.error = "boom"
    assert not run.score(r).passed


def test_report_lists_every_question():
    sources = [{"n": 1, "citation": "§ 205-7"}]
    results = [_result("[1] answer", sources, ["§ 205-7"]), _result("Not in the sources.", sources, ["§ 205-6"], ["24 hours"])]
    md = run.report(results, "http://x", {"env": "preview", "username": "u"}, run.dt.datetime(2026, 10, 3, 12, 0))
    assert md.startswith("# Staff eval results, 2026-10-03")
    assert "Passed: 1/2 (50%)" in md
    assert md.count("CEO mark: right / partial / wrong") == 2
    assert "| 2 | `q` | 2.5 | no | 0/1 | 0/1 | 0/1 |" in md
    assert '"not in the sources": 1' in md
    assert "—" not in md


# ---------------------------------------------------------------- full run (FAKE_AZURE)


def test_full_run_against_the_app(staff_client, monkeypatch, tmp_path):
    staff_client.post("/api/staff/logout", headers={"X-Requested-With": "wv"})
    monkeypatch.setenv("EVAL_STAFF_PASSWORD", PASSWORD)
    out = tmp_path / "results.md"
    code = run.main(
        ["--url", "http://testserver", "--user", "alice", "--only", "ch205-notice,zba-timing,penalty-tiers", "--out", str(out), "--delay", "0"],
        client=staff_client,
    )
    assert code == 0
    md = out.read_text()
    assert "signed in as `alice`" in md and "env `local`" in md
    assert md.count("CEO mark: right / partial / wrong") == 3
    raw = json.loads(out.with_suffix(".json").read_text())
    assert raw["summary"]["questions"] == 3
    for r in raw["results"]:
        assert r["mode"] == "staff"
        assert r["sources"], r["id"]
        assert r["answer"], r["id"]
        assert not r["error"], r["error"]
    # Logged out at the end.
    assert staff_client.get("/api/staff/me").status_code == 401


def test_bad_password_stops_the_run(client, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_STAFF_PASSWORD", "wrong password here")
    with pytest.raises(SystemExit, match="staff login failed \\(401\\)"):
        run.main(["--user", "alice", "--out", str(tmp_path / "r.md")], client=client)


def test_min_pass_sets_exit_status(staff_client, monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_STAFF_PASSWORD", PASSWORD)
    # The fake answers cannot carry every expected fact, so a 100% bar fails.
    code = run.main(["--user", "alice", "--only", "zba-timing", "--out", str(tmp_path / "r.md"), "--delay", "0", "--min-pass", "1.01"], client=staff_client)
    assert code == 1
