from sale_agent.eval.runner import EvalRunner


def test_eval_runner_isolated_and_reports_all_datasets():
    report = EvalRunner().run()
    assert report["eval_mode"] is True
    assert set(report["reports"]) == {"profile_eval", "tag_eval", "talk_eval"}
    assert report["reports"]["profile_eval"]["metrics"]["field_accuracy"] >= 0.9
    assert report["reports"]["tag_eval"]["metrics"]["tag_recall"] >= 0.9
    assert report["reports"]["talk_eval"]["metrics"]["helpfulness"] == 5.0


def test_eval_runner_baseline_diff(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"profile_eval": {"metrics": {"field_accuracy": 0.5}}}', encoding="utf-8")
    report = EvalRunner().run("profile_eval", baseline)
    assert report["baseline_diff"]["profile_eval"]["field_accuracy"] > 0
