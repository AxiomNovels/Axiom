"""Offline before/after latency measurements; never contacts external services.

Run from the repository root with backend/.venv/Scripts/python.exe and pass
--baseline <pre-change git revision>. CPU timings exclude database/network I/O.
The directory case injects a stated delay per auth call; it is not a production
latency measurement. Each case checks exact output equivalence before timing.
"""
import argparse
from copy import deepcopy
import gc
import inspect
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_PUBLISHABLE_KEY"] = "offline-benchmark"

# Initialize routes in their normal order before loading comparison modules.
import main  # noqa: E402, F401
from routes import search, users  # noqa: E402
from services import recommendation_service  # noqa: E402
from services.search_service import PROFILE_MEASURES  # noqa: E402


def baseline_module(revision, path):
    source = subprocess.check_output(
        ["git", "show", f"{revision}:{path}"], cwd=ROOT, encoding="utf-8",
    )
    module = ModuleType("baseline_" + Path(path).stem)
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def catalogue(count):
    rng = random.Random(42)
    tags = ["Magic", "Time Loop", "Academy", "Adventure", "System", "Mystery"]
    return [{
        "id": index, "title": f"Magic Academy {index:05}", "author": "Author",
        "synopsis": "A student learns magic and explores a strange world. " * 50,
        "tags": rng.sample(tags, 4), "genres": ["Fantasy"], "status": "ongoing",
        "protagonist_profiles": {key: rng.randrange(101) for key in PROFILE_MEASURES},
        "reviews": [{"rating": 4}, {"rating": 5}],
    } for index in range(count)]


def compare(label, before, after, repeats):
    assert before() == after(), f"Output mismatch: {label}"
    timings = [[], []]
    # Alternate order to reduce warm-up and ordering bias.
    for index in range(repeats):
        for slot in ([0, 1] if index % 2 else [1, 0]):
            start = time.perf_counter()
            (before, after)[slot]()
            timings[slot].append((time.perf_counter() - start) * 1000)
    peaks = []
    for call in (before, after):
        gc.collect()
        tracemalloc.start()
        call()
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    medians = [statistics.median(values) for values in timings]
    return {"case": label, "before_ms": round(medians[0], 3),
            "after_ms": round(medians[1], 3),
            "reduction_percent": round(100 * (1 - medians[1] / medians[0]), 1),
            "before_peak_bytes": peaks[0], "after_peak_bytes": peaks[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()
    old_search = baseline_module(args.baseline, "backend/routes/search.py")
    old_users = baseline_module(args.baseline, "backend/routes/users.py")
    old_recommend = baseline_module(args.baseline, "backend/services/recommendation_service.py")
    results = []
    for count in (1000, 10000):
        rows = catalogue(count)
        for module in (old_search, search):
            module._fetch_catalogue = lambda: rows
        parameters = {name: None for name in inspect.signature(search.search_novels).parameters
                      if name.endswith(("_min", "_max"))}
        parameters.update(request=None, q="magic academy", min_rating=None)
        results.append(compare(f"search relevance, {count} rows, all match",
                               lambda: old_search.search_novels(**parameters),
                               lambda: search.search_novels(**parameters), args.repeats))
        results.append(compare(f"recommendations, {count} rows, limit 6",
                               lambda: old_recommend.recommend_novels(rows[0], rows),
                               lambda: recommendation_service.recommend_novels(rows[0], rows),
                               args.repeats))

    # A controlled read substitute isolates avoided auth calls from real
    # network variation. Three fixed database queries have no injected delay.
    profiles = [{"id": str(i), "username": f"Reader {i:03}",
                 "online_status_visibility": "public"} for i in range(100)]
    query = SimpleNamespace()
    query.select = query.order = query.limit = lambda *_: query
    query.execute = lambda: SimpleNamespace(data=deepcopy(profiles))
    client = SimpleNamespace(table=lambda _: query)
    calls = [0, 0]
    for slot, module in enumerate((old_users, users)):
        module.create_service_client = lambda: client
        module._online_user_ids = lambda *_: set()
        module._presence_by_user_id = lambda *_: {}

        def special(_client, identity, slot=slot):
            calls[slot] += 1
            time.sleep(0.002)
            return identity == "0"

        module._is_special_account = special
    results.append(compare("directory 100 candidates / 48 results, simulated 2ms auth calls",
                           lambda: old_users.list_public_users(sort="last_online", limit=48),
                           lambda: users.list_public_users(sort="last_online", limit=48),
                           args.repeats))
    results[-1]["auth_calls_per_request_before"] = calls[0] // (args.repeats + 2)
    results[-1]["auth_calls_per_request_after"] = calls[1] // (args.repeats + 2)
    print(json.dumps({"baseline": args.baseline, "python": sys.version,
                      "repeats": args.repeats, "results": results}, indent=2))


if __name__ == "__main__":
    main()
