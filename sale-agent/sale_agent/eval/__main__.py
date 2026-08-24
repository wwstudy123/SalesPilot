from __future__ import annotations

import argparse
import json
from pathlib import Path

from sale_agent.eval.runner import EvalRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="SalesPilot M9 离线评测")
    parser.add_argument("--dataset", choices=("all", "profile_eval", "tag_eval", "talk_eval"), default="all")
    parser.add_argument("--output", default="output/eval/report.json")
    parser.add_argument("--baseline", default="output/eval/baseline.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = EvalRunner().run(args.dataset, Path(args.baseline))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"评测报告已写入：{output}")


if __name__ == "__main__":
    main()
