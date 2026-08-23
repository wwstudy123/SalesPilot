from __future__ import annotations

from sagt_agent.domain.runtime import Phase
from sagt_agent.store.store import Store


def build_resume_prompt(store: Store) -> tuple[str, str]:
    progress = store.progress.load()
    if progress is None:
        return "", ""
    if progress.phase == Phase.COMPLETE:
        return "", ""

    title = progress.project_name.strip() or "当前项目"
    lines: list[str] = ["[恢复指令]", "", f"项目「{title}」"]

    completed = len(progress.completed_sections)
    if completed > 0:
        msg = f"已完成 {completed} 节"
        if progress.total_sections > 0:
            msg += f"（共 {progress.total_sections} 节）"
        msg += f"，共 {progress.total_word_count} 字。"
        lines[-1] += msg

    label = "恢复"
    if progress.phase == Phase.PLANNING:
        lines.append("上次在规划阶段中断。请检查当前计划状态并继续。")
        label = "恢复：规划阶段"
    elif progress.phase == Phase.GENERATING:
        pending_checkpoint = store.signals.load_pending_checkpoint()
        pending_commit = store.signals.load_pending_commit()

        if pending_checkpoint is not None:
            lines.append(f"已完成第 {pending_checkpoint.pause_after_section} 节，正在等待用户确认是否继续。")
            lines.append(f"确认后将从第 {pending_checkpoint.next_section} 节继续。")
            label = f"恢复：第 {pending_checkpoint.pause_after_section} 节检查点待确认"
        elif pending_commit is not None:
            lines.append(f"第 {pending_commit.section} 节提交中途中断（阶段：{pending_commit.stage}）。请重新提交该节。")
            label = f"恢复：第 {pending_commit.section} 节提交中断"
        elif progress.pending_rewrites:
            lines.append(f"有 {len(progress.pending_rewrites)} 节待修订：{progress.pending_rewrites}。原因：{progress.rewrite_reason}。")
            label = f"修订恢复：{len(progress.pending_rewrites)} 节待处理"
        elif progress.in_progress_section > 0:
            lines.append(f"第 {progress.in_progress_section} 节生成中途中断，请重新生成该节。")
            label = f"恢复：第 {progress.in_progress_section} 节生成中断"
        else:
            next_section = progress.next_section()
            lines.append(f"请从第 {next_section} 节继续生成。")
            label = f"恢复：从第 {next_section} 节继续"
    else:
        lines.append("请从当前进度继续执行。")

    steer = store.run_meta.consume_pending_steer()
    if steer:
        lines.append(f"[用户干预] {steer}")

    return "\n".join(lines), label
