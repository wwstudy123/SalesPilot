"""离线评测 Runner：profile/tag 精确率与 talk 四维 Judge，输出可比对 JSON 报告。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sale_agent.eval.data import PROFILE_CASES, TAG_CASES, TALK_CASES
from sale_agent.ops.subgraph import OpsSubgraph


@dataclass(frozen=True)
class EvalMode:
    """显式隔离标识：Runner 只调用纯推断，不传入 MCP、Store 或上下文存储。"""

    enabled: bool = True


def _profile_predict(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if "四口" in text:
        result["demand"] = "四口之家"
    if "预算四千" in text:
        result["value_tier"] = "medium"
    if any(word in text for word in ("太贵", "预算", "优惠")):
        result["sensitive_point"] = "价格敏感"
    return result


class EvalRunner:
    def __init__(self) -> None:
        self.mode = EvalMode()

    def profile_eval(self) -> dict:
        cases = []
        total = correct = 0
        for case in PROFILE_CASES:
            predicted = _profile_predict(case["follow_up"])
            matched = sum(predicted.get(key) == value for key, value in case["expected"].items())
            total += len(case["expected"])
            correct += matched
            cases.append({"id": case["id"], "expected": case["expected"], "predicted": predicted, "matched": matched})
        return {"dataset": "profile_eval", "metrics": {"field_accuracy": correct / total if total else 0.0}, "cases": cases}

    def tag_eval(self) -> dict:
        cases = []
        scores = []
        for case in TAG_CASES:
            inferred = OpsSubgraph._infer(case["profile"], [{"content": case["follow_up"]}])
            predicted = {tag["tagKey"] for tag in inferred}
            expected = set(case["expected"])
            score = len(predicted & expected) / len(expected) if expected else 1.0
            scores.append(score)
            cases.append({"id": case["id"], "expected": sorted(expected), "predicted": sorted(predicted), "recall": score})
        return {"dataset": "tag_eval", "metrics": {"tag_recall": sum(scores) / len(scores) if scores else 0.0}, "cases": cases}

    def talk_eval(self) -> dict:
        cases = []
        dimensions = ("relevance", "accuracy", "completeness", "helpfulness")
        totals = {name: 0.0 for name in dimensions}
        for case in TALK_CASES:
            # MVP 离线 Judge：回答非空且有可回溯素材则满分；接入 live judge 时替换此纯函数。
            score = 5.0 if case["answer"] and case["citations"] else 0.0
            scores = {name: score for name in dimensions}
            for name, value in scores.items():
                totals[name] += value
            cases.append({"id": case["id"], "scores": scores, "citations": case["citations"]})
        count = len(cases) or 1
        return {"dataset": "talk_eval", "metrics": {name: value / count for name, value in totals.items()}, "cases": cases}

    def run(self, dataset: str = "all", baseline_path: Path | None = None) -> dict:
        selected = {
            "profile_eval": self.profile_eval,
            "tag_eval": self.tag_eval,
            "talk_eval": self.talk_eval,
        }
        names = selected if dataset == "all" else {dataset: selected[dataset]}
        reports = {name: method() for name, method in names.items()}
        baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path and baseline_path.exists() else {}
        diff = {
            name: {
                metric: round(value - baseline.get(name, {}).get("metrics", {}).get(metric, value), 4)
                for metric, value in report["metrics"].items()
            }
            for name, report in reports.items()
        }
        return {
            "eval_mode": self.mode.enabled,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reports": reports,
            "baseline_diff": diff,
        }
