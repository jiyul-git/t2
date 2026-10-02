#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "gto_db"
MASTER = DB / "index_9max_operational_v1.json"

def eq_num(a, b, tol=1e-9):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False

def main():
    ap = argparse.ArgumentParser(description="Query provenance-free 9-max operational GTO rows")
    ap.add_argument("--stack", type=float)
    ap.add_argument("--hand")
    ap.add_argument("--hero")
    ap.add_argument("--family")
    ap.add_argument("--villain")
    ap.add_argument("--shover")
    ap.add_argument("--ante-model")
    ap.add_argument("--history-contains")
    ap.add_argument("--dataset", action="append", help="exact dataset filename; repeatable")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--count-only", action="store_true")
    args = ap.parse_args()

    idx = json.loads(MASTER.read_text(encoding="utf-8"))
    datasets = list(idx["datasets"])
    if args.dataset:
        wanted = set(args.dataset)
        missing = wanted - set(datasets)
        if missing:
            raise SystemExit(f"unknown dataset(s): {sorted(missing)}")
        datasets = [x for x in datasets if x in wanted]

    out = []
    count = 0
    for name in datasets:
        path = DB / name
        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if args.stack is not None and not eq_num(row.get("stack_bb"), args.stack):
                    continue
                if args.hand is not None and row.get("hand_class") != args.hand:
                    continue
                if args.hero is not None and row.get("hero_position") != args.hero:
                    continue
                if args.family is not None and row.get("action_family") != args.family:
                    continue
                if args.villain is not None and row.get("villain_position") != args.villain:
                    continue
                if args.shover is not None and row.get("shover_position") != args.shover:
                    continue
                if args.ante_model is not None and row.get("ante_model") != args.ante_model:
                    continue
                if args.history_contains is not None and args.history_contains not in str(row.get("action_history_key", "")):
                    continue
                count += 1
                if not args.count_only and len(out) < args.limit:
                    out.append({"dataset": name, **row})

    if args.count_only:
        print(count)
        return

    print(json.dumps({
        "query": {
            "stack": args.stack,
            "hand": args.hand,
            "hero": args.hero,
            "family": args.family,
            "villain": args.villain,
            "shover": args.shover,
            "ante_model": args.ante_model,
            "history_contains": args.history_contains,
        },
        "match_count": count,
        "returned": len(out),
        "rows": out,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
