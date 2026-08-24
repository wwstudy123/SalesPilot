"""Coach 子图：话术生成（架构 §7.1，MVP 最重链路）。

流程：装配技能配置 → MCP 读画像+跟进（事实区）→ RAG playbook_kb（话术区，引用 [c*]）
→ 生成 → 事实自检（与画像冲突检测）→ 建议卡落库。
纪律：客户事实一律来自 MCP/画像，RAG 只出话术与方法论；无命中标注"通用建议"。
"""

from __future__ import annotations

from sale_agent.ai.gateway import LLMGateway
from sale_agent.ai.trace import TraceStore
from sale_agent.coach.skills import select_skill
from sale_agent.profile.mcp_client import McpClient, McpError
from sale_agent.rag.pipeline import RAGPipeline
from sale_agent.suggestion.store import SuggestionStore

# 价值分层 → 产品推荐（事实自检基准：推荐必须与分层一致）
TIER_PRODUCT = {
    "high": "泉净 X1200 Pro 旗舰款",
    "medium": "泉净 X800",
    "low": "泉净 X400",
}
TIER_PITCH = {
    "high": "结合您的使用规模，旗舰款的双出水与五年长效滤芯更匹配。",
    "medium": "综合预算与需求，主力款 800G 大通量是均衡之选。",
    "low": "从实用出发，入门款即可满足日常直饮，后续随时可升级。",
}
# 敏感点含催促类关键词时，促单类话术需剔除（冲突降级）
_URGE_KEYWORDS = ("催", "逼单", "别催")
_PUSH_KEYWORDS = ("留上", "名额", "过了这村", "今天定")
_PRODUCT_KEYWORDS = ("产品", "机型", "型号", "参数", "滤芯", "通量", "废水", "安装", "保修", "售后", "价格", "X400", "X600", "X800", "X1200")


class CoachSubgraph:
    def __init__(
        self, mcp: McpClient, rag: RAGPipeline, suggestions: SuggestionStore, gateway: LLMGateway, trace: TraceStore | None = None
    ) -> None:
        self._mcp = mcp
        self._rag = rag
        self._suggestions = suggestions
        self._gateway = gateway
        self._trace = trace

    # ---------- 主入口 ----------

    def generate(
        self,
        *,
        intent: str,
        message: str,
        customer_id: int | None,
        employee_id: int,
        jwt: str | None,
        session_id: str,
        run_id: str,
        exclude_chunk_ids: list[int] | None = None,
        requirement: str | None = None,
        ephemeral: bool = False,
    ) -> dict:
        """生成话术建议；exclude_chunk_ids 供重新生成换素材，ephemeral 不落建议卡。"""
        skill = select_skill(intent)
        tool_calls: list[dict] = []
        warnings: list[str] = []

        # 1) 事实装载（事实区，来自 MCP；失败降级通用建议不阻断）
        profile, follow_ups = self._load_facts(customer_id, jwt, tool_calls, warnings)

        # 2) RAG 知识区（话术为主；产品诉求补充 product_kb）
        query = f"{message}。{requirement}" if requirement else message
        rag_result = self._rag.retrieve(query, domain="playbook", customer_ctx=profile)
        if self._needs_product_knowledge(query):
            product_result = self._rag.retrieve(query, domain="product", customer_ctx=profile)
            # 产品事实最多占两个引用位，保留至少三条话术素材供 Coach 组织表达。
            rag_result.hits = product_result.hits[:2] + rag_result.hits[:3]
            rag_result.knowledge_zone, rag_result.citations = self._rag.reinject(rag_result.hits)
            if product_result.mode == "listwise":
                rag_result.mode = "listwise"
        if exclude_chunk_ids:
            rag_result.hits = [hit for hit in rag_result.hits if hit.chunk_id not in exclude_chunk_ids]
            rag_result.knowledge_zone, rag_result.citations = self._rag.reinject(rag_result.hits)
        if not rag_result.citations:
            warnings.append("知识库未命中，以下为通用建议，请结合实际情况判断")

        # 3) 生成（echo 确定性模板；live 走 gateway）
        reply = self._compose(skill, message, profile, follow_ups, rag_result)

        # 4) 事实自检：与画像冲突检测（架构安全钩子）
        reply, self_check = self._self_check(reply, profile)
        warnings.extend(self_check)

        # 5) 建议卡落库（ephemeral 重新生成场景不落卡，由路由回填原卡）
        suggestion_id = None
        if not ephemeral:
            suggestion = self._suggestions.create(
                customer_id=customer_id or 0,
                employee_id=employee_id,
                session_id=session_id,
                run_id=run_id,
                skill=skill["id"],
                request_message=message,
                content=reply,
                citations=rag_result.citations,
                warnings=warnings,
            )
            suggestion_id = suggestion["id"]
        return {
            "skill": skill,
            "reply": reply,
            "citations": rag_result.citations,
            "warnings": warnings,
            "suggestion_id": suggestion_id,
            "tool_calls": tool_calls,
            "rag_mode": rag_result.mode,
            "echo": self._gateway.settings.echo_mode,
        }

    @staticmethod
    def _needs_product_knowledge(query: str) -> bool:
        return any(keyword.lower() in query.lower() for keyword in _PRODUCT_KEYWORDS)

    # ---------- 事实装载 ----------

    def _load_facts(self, customer_id: int | None, jwt: str | None, tool_calls: list[dict], warnings: list[str]) -> tuple[dict, list[dict]]:
        profile: dict = {}
        follow_ups: list[dict] = []
        if not customer_id or not jwt:
            warnings.append("未提供客户上下文，未装载客户事实")
            return profile, follow_ups
        for tool, loader in (
            ("get_customer_profile", lambda: self._mcp.get_profile(customer_id, jwt)),
            ("list_follow_ups", lambda: self._mcp.list_follow_ups(customer_id, jwt)),
        ):
            try:
                data = loader()
                tool_calls.append({"tool": tool, "ok": True})
                if tool == "get_customer_profile":
                    profile = {field["fieldKey"]: field.get("fieldValue", "") for field in data}
                else:
                    follow_ups = data
            except McpError as exc:
                tool_calls.append({"tool": tool, "ok": False, "code": exc.code})
                warnings.append(f"{tool} 拉取失败（{exc.code}），建议不附带客户个性化内容")
        return profile, follow_ups

    # ---------- 生成（echo 确定性模板） ----------

    def _compose(self, skill: dict, message: str, profile: dict, follow_ups: list[dict], rag_result) -> str:
        if not self._gateway.settings.echo_mode:
            return self._compose_llm(skill, message, profile, follow_ups, rag_result)
        lines = [f"【{skill['label']}】", ""]
        if profile:
            facts = [f"{key}：{value}" for key, value in list(profile.items())[:4] if value]
            if facts:
                lines.append("客户画像要点：" + "；".join(facts))
        recent = follow_ups[:2]
        if recent:
            lines.append("最近跟进：" + "｜".join(f"{item.get('channel', '')} {str(item.get('content', ''))[:40]}" for item in recent))
        lines.append("")
        lines.append("建议话术：")
        if rag_result.citations:
            for citation, hit in zip(rag_result.citations, rag_result.hits[: len(rag_result.citations)]):
                talk = hit.content.split("话术：", 1)[-1] if "话术：" in hit.content else hit.content
                lines.append(f"- [{citation['label']}] {talk}")
        else:
            lines.append("- （通用建议）先倾听客户当前顾虑，再给出针对性方案，避免直接推销。")
        tier = profile.get("value_tier")
        if tier in TIER_PRODUCT:
            lines.append("")
            lines.append(f"产品匹配：推荐{TIER_PRODUCT[tier]}。{TIER_PITCH[tier]}")
        lines.append("")
        lines.append("提示：以上内容含 AI 生成成分，发送前请结合客户实际情况核对。")
        return "\n".join(lines)

    def _compose_llm(self, skill: dict, message: str, profile: dict, follow_ups: list[dict], rag_result) -> str:
        system = (
            f"你是零售销售话术教练（技能：{skill['label']}）。"
            "仅基于下方客户事实与知识库素材生成话术，引用素材须保留 [c*] 角标；"
            "素材不足时输出通用建议并明说，不得编造客户事实或产品参数。"
        )
        context = (
            f"员工诉求：{message}\n\n【客户事实区】\n画像：{profile}\n最近跟进：{follow_ups[:3]}"
            f"\n\n【知识区（话术素材）】\n{rag_result.knowledge_zone or '（无命中）'}"
        )
        result = self._gateway.chat([{"role": "system", "content": system}, {"role": "user", "content": context}])
        return result.content

    # ---------- 事实自检 ----------

    @staticmethod
    def _self_check(reply: str, profile: dict) -> tuple[str, list[str]]:
        warnings: list[str] = []
        # 规则一：敏感点反感催促 → 剔除促单类句子（冲突降级）
        sensitive = str(profile.get("sensitive_point", ""))
        if any(keyword in sensitive for keyword in _URGE_KEYWORDS):
            kept = []
            for line in reply.split("\n"):
                if any(keyword in line for keyword in _PUSH_KEYWORDS):
                    warnings.append("检测到客户敏感点反感催促，已剔除促单类表述")
                    continue
                kept.append(line)
            reply = "\n".join(kept)
        # 规则二：价值分层与推荐产品一致性（echo 模板确定性生成，此处为兜底校验）
        tier = profile.get("value_tier")
        if tier == "low" and ("X1200" in reply or "旗舰" in reply):
            warnings.append("推荐产品与客户价值分层不符，请人工复核")
        return reply, warnings

    # ---------- 注入（复用 rag 格式化） ----------

    def reinject(self, hits) -> tuple[str, list[dict]]:
        return self._rag.reinject(hits)
