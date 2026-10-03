"""Staff eval: ask the 30 questions in eval/questions.yaml in staff mode and score the citations.

    uv run python eval/run.py --url https://waterville-preview.<env>.azurecontainerapps.io
    uv run python eval/run.py --url http://localhost:8118 --user alice --only penalty-tiers,zba-timing

Signs in as a staff user (POST /api/staff/login), sends each question to
POST /api/chat with mode "staff", reads the SSE stream and scores it:

  cited      an expected citation is among the sources the answer cites with [n]
  mentioned  the answer text names it (e.g. "§ 205-7A" for "§ 205-7")
  retrieved  it is among the sources the search returned, cited or not
  facts      the answer contains each expected figure or phrase

An expected citation counts as a hit when it is cited, or mentioned and
retrieved. A question passes when every expected citation is a hit, every fact
is found and the stream ended without an error. The report also leaves a
right/partial/wrong column for the Code Enforcement Officer to mark by hand,
which is the pilot's citation accuracy measure (target 90% right).

Password: --password-file (default ~/waterville-preview-credentials.txt, the
file infra/deploy-preview.sh writes, read from its "Password:" line) or the
EVAL_STAFF_PASSWORD environment variable. Never pass it on the command line.

Writes eval/results-<date>.md (and the raw .json next to it). Exit status 0,
or 1 when --min-pass is given and fewer questions passed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

import httpx
import yaml

HERE = Path(__file__).resolve().parent
CSRF = {"X-Requested-With": "wv"}
DEFAULT_CREDENTIALS = Path.home() / "waterville-preview-credentials.txt"

# Same reading of [n] and [n.sub] markers as app/routers/chat.py.
CITE_RE = re.compile(r"\[(\d+)(?:\.[^\]]*)?\]")


# ---------------------------------------------------------------- questions


@dataclass
class Question:
    id: str
    question: str
    expect: list[list[str]]  # each entry: alternatives, any one counts
    facts: list[str] = field(default_factory=list)
    step: str = ""
    note: str = ""


def load_questions(path: Path) -> list[Question]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out, seen = [], set()
    for raw in data["questions"]:
        unknown = set(raw) - {"id", "question", "expect", "facts", "step", "note"}
        if unknown:
            raise ValueError(f"{raw.get('id')}: unknown fields {sorted(unknown)}")
        qid = str(raw["id"])
        if qid in seen:
            raise ValueError(f"duplicate id {qid}")
        seen.add(qid)
        expect = [[alt.strip() for alt in str(e).split("|") if alt.strip()] for e in raw.get("expect") or []]
        if not expect:
            raise ValueError(f"{qid}: no expected citations")
        facts = [str(f) for f in raw.get("facts") or []]
        for f in facts:
            re.compile(f)
        out.append(Question(qid, str(raw["question"]).strip(), expect, facts, str(raw.get("step", "")), str(raw.get("note", ""))))
    return out


# ---------------------------------------------------------------- citation matching


def norm_cite(s: str) -> str:
    """Collapse spacing so "§205-7", "§ 205-7" and "Sec. 205-7" compare equal."""
    s = (s or "").replace("\u00a0", " ").strip()
    s = re.sub(r"^(?:sec(?:tion)?\.?|§)\s*(?=\d)", "§ ", s, flags=re.I)
    s = re.sub(r"§\s*", "§ ", s)
    return re.sub(r"\s+", " ", s)


def cite_matches(expected: str, actual: str | None) -> bool:
    """`actual` is the expected citation or a subsection of it.

    "§ 205-7" matches "§ 205-7" and "§ 205-7A" but not "§ 205-70" or
    "§ 205-7.1"; "30-A M.R.S. § 4452" matches "30-A M.R.S. § 4452(3)".
    """
    if not actual:
        return False
    e, a = norm_cite(expected).lower(), norm_cite(actual).lower()
    if a == e:
        return True
    if not a.startswith(e):
        return False
    rest = a[len(e) :]
    if e[-1].isdigit():
        return not (rest[0].isdigit() or (rest[0] == "." and len(rest) > 1 and rest[1].isdigit()) or rest[0] == "-")
    return rest[0] in " .,:;(" or not rest[0].isalnum()


def mentioned(expected: str, text: str) -> bool:
    """The answer text names the citation (or a subsection of it)."""
    e = norm_cite(expected)
    # Statutes and rules are often written without the code name in the text
    # ("§ 4452(3)"); a city section is unambiguous on its own.
    pattern = re.escape(e).replace(r"\ ", r"\s*")
    pattern = pattern.replace("§", r"(?:§|sec(?:tion)?\.?)")
    tail = r"(?![0-9]|\.[0-9]|-[0-9])" if e[-1].isdigit() else r"(?![A-Za-z0-9])"
    return re.search(pattern + tail, text, flags=re.I) is not None


# ---------------------------------------------------------------- SSE


def read_sse(lines: Iterable[str]) -> Iterator[tuple[str, object]]:
    """Events from a text/event-stream, as (event, parsed data)."""
    event, data = "message", []
    for line in lines:
        line = line.rstrip("\r")
        if not line:
            if data:
                raw = "\n".join(data)
                try:
                    yield event, json.loads(raw)
                except json.JSONDecodeError:
                    yield event, raw
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        raw = "\n".join(data)
        try:
            yield event, json.loads(raw)
        except json.JSONDecodeError:
            yield event, raw


# ---------------------------------------------------------------- scoring


@dataclass
class Result:
    id: str
    step: str
    question: str
    expect: list[list[str]]
    facts: list[str]
    answer: str = ""
    mode: str = ""
    sources: list[dict] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)
    error: str = ""
    seconds: float = 0.0
    first_token: float | None = None
    # scoring
    hits: list[dict] = field(default_factory=list)
    facts_found: list[bool] = field(default_factory=list)
    passed: bool = False


def score(r: Result) -> Result:
    cited_sources = [s for s in r.sources if s.get("n") in set(r.cited)]
    r.hits = []
    for alts in r.expect:
        cited = next((a for a in alts if any(cite_matches(a, s.get("citation")) for s in cited_sources)), None)
        retrieved = next((a for a in alts if any(cite_matches(a, s.get("citation")) for s in r.sources)), None)
        named = next((a for a in alts if mentioned(a, r.answer)), None)
        hit = bool(cited or (named and retrieved))
        r.hits.append(
            {
                "expect": " | ".join(alts),
                "cited": bool(cited),
                "retrieved": bool(retrieved),
                "mentioned": bool(named),
                "hit": hit,
            }
        )
    r.facts_found = [re.search(f, r.answer, flags=re.I) is not None for f in r.facts]
    r.passed = not r.error and bool(r.answer) and all(h["hit"] for h in r.hits) and all(r.facts_found)
    return r


# ---------------------------------------------------------------- client


def login(client: httpx.Client, user: str, password: str) -> dict:
    r = client.post("/api/staff/login", json={"username": user, "password": password}, headers=CSRF)
    if r.status_code != 200:
        detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
        raise SystemExit(f"staff login failed ({r.status_code}): {detail}")
    me = client.get("/api/staff/me")
    me.raise_for_status()
    return me.json()


def ask(client: httpx.Client, q: Question, mode: str = "staff", timeout: float = 240.0, retries: int = 3) -> Result:
    r = Result(q.id, q.step, q.question, q.expect, q.facts)
    body = {"messages": [{"role": "user", "content": q.question}], "mode": mode}
    headers = {**CSRF, "Accept": "text/event-stream"}
    for attempt in range(retries + 1):
        start = time.monotonic()
        parts: list[str] = []
        try:
            with client.stream("POST", "/api/chat", json=body, headers=headers, timeout=timeout) as resp:
                if resp.status_code == 429 and attempt < retries:
                    time.sleep(min(60, 15 * (attempt + 1)))
                    continue
                if resp.status_code != 200:
                    resp.read()
                    r.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    break
                for event, data in read_sse(resp.iter_lines()):
                    if event == "meta" and isinstance(data, dict):
                        r.mode = data.get("mode", "")
                    elif event == "sources" and isinstance(data, list):
                        r.sources = data
                    elif event == "delta" and isinstance(data, dict):
                        if r.first_token is None:
                            r.first_token = round(time.monotonic() - start, 2)
                        parts.append(data.get("text", ""))
                    elif event == "error":
                        r.error = (data.get("message") if isinstance(data, dict) else str(data)) or "error"
            r.answer = "".join(parts)
            r.seconds = round(time.monotonic() - start, 2)
            break
        except httpx.HTTPError as e:
            r.error = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(5)
                continue
    r.cited = sorted({int(n) for n in CITE_RE.findall(r.answer) if 1 <= int(n) <= len(r.sources)})
    if mode == "staff" and r.mode and r.mode != "staff" and not r.error:
        r.error = f"answered in {r.mode} mode"
    return score(r)


# ---------------------------------------------------------------- report


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def summary(results: list[Result]) -> dict:
    hits = [h for r in results for h in r.hits]
    facts = [f for r in results for f in r.facts_found]
    timed = [r.seconds for r in results if not r.error]
    return {
        "questions": len(results),
        "passed": sum(r.passed for r in results),
        "citations": len(hits),
        "hit": sum(h["hit"] for h in hits),
        "cited": sum(h["cited"] for h in hits),
        "retrieved": sum(h["retrieved"] for h in hits),
        "facts": len(facts),
        "facts_found": sum(facts),
        "errors": sum(bool(r.error) for r in results),
        "no_answer": sum(bool(re.search(r"not in the sources", r.answer, re.I)) for r in results),
        "mean_seconds": round(sum(timed) / len(timed), 1) if timed else None,
    }


def report(results: list[Result], url: str, me: dict, started: dt.datetime) -> str:
    s = summary(results)
    lines = [
        f"# Staff eval results, {started:%Y-%m-%d}",
        "",
        f"- Target: {url} (env `{me.get('env', '?')}`, signed in as `{me.get('username', '?')}`)",
        f"- Run: {started:%Y-%m-%d %H:%M} UTC, {s['questions']} questions from `eval/questions.yaml`",
        f"- Passed: {_pct(s['passed'], s['questions'])}",
        f"- Expected citations hit (cited, or named and retrieved): {_pct(s['hit'], s['citations'])}",
        f"- Expected citations cited with [n]: {_pct(s['cited'], s['citations'])}",
        f"- Expected citations retrieved by the search: {_pct(s['retrieved'], s['citations'])}",
        f"- Facts found: {_pct(s['facts_found'], s['facts'])}",
        f"- Errors: {s['errors']}. Answers saying \"not in the sources\": {s['no_answer']}",
        f"- Mean time per answer: {s['mean_seconds']} s" if s["mean_seconds"] is not None else "- Mean time per answer: n/a",
        "",
        "Automatic scores check where an answer points, not whether it is right. The CEO marks each answer",
        "right, partial or wrong in the last column; the pilot target is 90% or more right.",
        "",
        "| # | Question | Step | Pass | Citations hit | Retrieved | Facts | Seconds | Missing | CEO mark |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        missing = [h["expect"] for h in r.hits if not h["hit"]]
        missing += [f"fact /{f}/" for f, ok in zip(r.facts, r.facts_found) if not ok]
        if r.error:
            missing.insert(0, f"error: {r.error}")
        lines.append(
            f"| {i} | `{r.id}` | {r.step} | {'yes' if r.passed else 'no'} "
            f"| {sum(h['hit'] for h in r.hits)}/{len(r.hits)} | {sum(h['retrieved'] for h in r.hits)}/{len(r.hits)} "
            f"| {sum(r.facts_found)}/{len(r.facts)} | {r.seconds:.1f} | {_cell('; '.join(missing)) or ''} | |"
        )
    lines += ["", "## Answers", ""]
    for i, r in enumerate(results, 1):
        cited = [s for s in r.sources if s.get("n") in set(r.cited)]
        lines += [
            f"### {i}. `{r.id}` ({'pass' if r.passed else 'fail'})",
            "",
            f"**Question.** {r.question}",
            "",
            "**Expected.** " + "; ".join(" or ".join(a) for a in r.expect) + (f" Facts: {', '.join('/' + f + '/' for f in r.facts)}." if r.facts else ""),
            "",
            "**Cited.** " + ("; ".join(f"[{s['n']}] {s.get('citation') or s.get('title')}" for s in cited) or "none"),
            "",
            "**Retrieved.** " + ("; ".join(f"[{s['n']}] {s.get('citation') or s.get('title')}" for s in r.sources) or "none"),
            "",
        ]
        if r.error:
            lines += [f"**Error.** {r.error}", ""]
        answer = r.answer.strip() or "(no answer)"
        lines += ["**Answer.**", ""] + [f"> {ln}" if ln else ">" for ln in answer.splitlines()] + ["", "CEO mark: right / partial / wrong", ""]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main


def read_password(path: Path | None) -> str:
    if pw := os.environ.get("EVAL_STAFF_PASSWORD"):
        return pw
    if path and path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Password:"):
                return line.split(":", 1)[1].strip()
    raise SystemExit(f"no staff password: set EVAL_STAFF_PASSWORD or pass --password-file (looked in {path})")


def output_path(out: str | None, started: dt.datetime) -> Path:
    if out:
        return Path(out)
    p = HERE / f"results-{started:%Y-%m-%d}.md"
    return p if not p.exists() else HERE / f"results-{started:%Y-%m-%d-%H%M}.md"


def main(argv: list[str] | None = None, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("EVAL_URL", "http://localhost:8000"))
    ap.add_argument("--user", default=os.environ.get("EVAL_STAFF_USER", "inspector"))
    ap.add_argument("--password-file", type=Path, default=DEFAULT_CREDENTIALS)
    ap.add_argument("--questions", type=Path, default=HERE / "questions.yaml")
    ap.add_argument("--only", help="comma-separated question ids")
    ap.add_argument("--out", help="report path (default eval/results-<date>.md)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between questions")
    ap.add_argument("--timeout", type=float, default=240.0)
    ap.add_argument("--min-pass", type=float, help="exit 1 when the pass rate is below this fraction")
    args = ap.parse_args(argv)

    questions = load_questions(args.questions)
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        unknown = wanted - {q.id for q in questions}
        if unknown:
            raise SystemExit(f"unknown question ids: {', '.join(sorted(unknown))}")
        questions = [q for q in questions if q.id in wanted]

    password = read_password(args.password_file)
    started = dt.datetime.now(dt.timezone.utc)
    own = client is None
    client = client or httpx.Client(base_url=args.url.rstrip("/"), timeout=args.timeout, follow_redirects=False)
    try:
        me = login(client, args.user, password)
        if me.get("env") == "production":
            print("note: the target reports env 'production'", file=sys.stderr)
        results = []
        for i, q in enumerate(questions, 1):
            if i > 1 and args.delay:
                time.sleep(args.delay)
            r = ask(client, q, timeout=args.timeout)
            results.append(r)
            flag = "pass" if r.passed else "FAIL"
            print(f"[{i:2}/{len(questions)}] {flag} {q.id} ({r.seconds:.1f}s){' ' + r.error if r.error else ''}", file=sys.stderr)
        try:
            client.post("/api/staff/logout", headers=CSRF)
        except httpx.HTTPError:
            pass
    finally:
        if own:
            client.close()

    out = output_path(args.out, started)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(results, args.url, me, started), encoding="utf-8")
    raw = {"url": args.url, "started": started.isoformat(), "env": me.get("env"), "summary": summary(results), "results": [asdict(r) for r in results]}
    out.with_suffix(".json").write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
    s = summary(results)
    print(f"{s['passed']}/{s['questions']} passed, citations hit {s['hit']}/{s['citations']}; report: {out}", file=sys.stderr)
    if args.min_pass is not None and s["questions"] and s["passed"] / s["questions"] < args.min_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
