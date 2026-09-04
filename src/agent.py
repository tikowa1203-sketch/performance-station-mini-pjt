from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from .agents import BedrockSynthesizer, ExecutionPlan, Supervisor, render_draft
from .config import Settings, settings as default_settings
from .guardrails import inspect_input, safe_output
from .memory import ConversationMemory
from .schemas import ContextItem, QueryResponse, Route
from .tools import PerformanceTools, extract_run_id
from .tracing import TraceRecorder


class PerformanceStationAgent:
    """Supervisor가 전문 Agent/Tool을 조합하는 Performance Station Copilot."""

    def __init__(self, settings: Settings = default_settings, profile: str = "round2"):
        if profile not in {"round1", "round2"}:
            raise ValueError("profile은 round1 또는 round2여야 합니다.")
        self.settings = settings
        self.profile = profile
        self.supervisor = Supervisor(settings)
        self.tools = PerformanceTools(settings.data_dir)
        self.memory = ConversationMemory()
        self.synthesizer = BedrockSynthesizer(settings)
        self.pending: dict[str, dict[str, Any]] = {}
        self._pending_lock = threading.Lock()

    def query(self, question: str, session_id: str = "default") -> QueryResponse:
        original_question = question
        recorder = TraceRecorder(self.settings.trace_path, session_id)
        with recorder.span("guardrail.input", question) as span:
            guard = inspect_input(question)
            span["output"] = {
                "allowed": guard.allowed,
                "reason": guard.reason,
                "risky_action": guard.risky_action,
            }

        if not guard.allowed:
            answer = (
                f"요청을 거부합니다. 요청을 처리할 수 없습니다. 사유: {guard.reason}. "
                "Performance Station의 성능테스트·병목·가용성 질문은 계속 도와드릴 수 있습니다."
            )
            recorder.add("guardrail.output", "blocked", answer)
            return QueryResponse(answer=answer, trace=recorder.items, route=Route.BLOCKED)

        question = guard.sanitized_text
        with recorder.span("supervisor.route", question) as span:
            decision = self.supervisor.route(question, guard.risky_action)
            span["output"] = decision.model_dump()

        plan = self.supervisor.make_plan(decision, self.profile)
        recorder.add("plan.execute", question, {"steps": plan.steps, "tools": plan.tools})

        evidence, contexts, tools_used = self._execute(plan, question, recorder)

        if decision.route == Route.CHANGE:
            approval_id = str(uuid.uuid4())
            with self._pending_lock:
                self.pending[approval_id] = {
                    "question": question,
                    "session_id": session_id,
                    "plan": evidence.get("change_plan", {}),
                }
            answer = self._change_answer(evidence)
            answer = safe_output(answer)
            recorder.add("hitl.interrupt", question, {"approval_id": approval_id})
            self.memory.add(session_id, question, answer)
            return QueryResponse(
                answer=answer,
                contexts=contexts,
                trace=recorder.items,
                route=decision.route,
                tools_used=tools_used,
                status="approval_required",
                approval_id=approval_id,
            )

        with recorder.span(f"agent.{decision.route.value}.synthesize", evidence) as span:
            if self.settings.use_bedrock:
                draft = self.synthesizer.synthesize(
                    question, decision.route, evidence, self.memory.summary(session_id)
                )
                answer = render_draft(draft)
            else:
                answer = self._offline_answer(question, decision.route, evidence)
            if original_question != question:
                answer += "\n\n개인정보 마스킹 처리: 입력에 포함된 연락처 등은 [PHONE]과 같은 비식별 값으로 치환했습니다."
            answer = safe_output(answer)
            span["output"] = answer

        self.memory.add(session_id, question, answer)
        return QueryResponse(
            answer=answer,
            contexts=contexts,
            trace=recorder.items,
            route=decision.route,
            tools_used=tools_used,
        )

    def approve(self, approval_id: str, approved: bool, reviewer: str) -> QueryResponse:
        with self._pending_lock:
            request = self.pending.pop(approval_id, None)
        if not request:
            return QueryResponse(
                answer="승인 요청을 찾을 수 없거나 이미 처리되었습니다.",
                route=Route.CHANGE,
                status="not_found",
            )
        recorder = TraceRecorder(self.settings.trace_path, request["session_id"])
        recorder.add(
            "hitl.resume",
            {"approval_id": approval_id},
            {"approved": approved, "reviewer": reviewer},
        )
        if not approved:
            answer = "변경 요청이 반려되었습니다. 어떤 운영 변경도 실행하지 않았습니다."
            status = "rejected"
        else:
            answer = (
                "변경 계획이 승인되었습니다. 이 미니 프로젝트는 실제 운영 시스템에 연결되지 않아 "
                "변경을 실행하지 않고, 승인 기록과 실행 전 체크리스트까지만 제공합니다."
            )
            status = "approved_dry_run"
        return QueryResponse(
            answer=answer,
            trace=recorder.items,
            route=Route.CHANGE,
            status=status,
        )

    def _execute(
        self, plan: ExecutionPlan, question: str, recorder: TraceRecorder
    ) -> tuple[dict[str, Any], list[ContextItem], list[str]]:
        evidence: dict[str, Any] = {}
        contexts: list[ContextItem] = []
        used: list[str] = []

        if "retrieve_docs" in plan.tools:
            with recorder.span("tool.retrieve_docs", question) as span:
                contexts = self.tools.retrieve_docs(
                    question,
                    top_k=2 if self.profile == "round1" else self.settings.top_k,
                    use_expansion=self.profile == "round2",
                )
                evidence["documents"] = [item.model_dump() for item in contexts]
                span["output"] = [item.doc_id for item in contexts]
            used.append("retrieve_docs")

        run_id = extract_run_id(question)
        run: dict[str, Any] | None = None
        if "get_test_run" in plan.tools:
            with recorder.span("tool.get_test_run", run_id or "missing") as span:
                run = self.tools.get_test_run(run_id) if run_id else {
                    "error": "분석할 테스트 ID가 필요합니다."
                }
                evidence["run"] = run
                span["output"] = run
            used.append("get_test_run")

        if "calculate_kpis" in plan.tools and run is not None:
            with recorder.span("tool.calculate_kpis", run_id or "missing") as span:
                evidence["kpis"] = self.tools.calculate_kpis(run)
                span["output"] = evidence["kpis"]
            used.append("calculate_kpis")

        if "find_similar_incidents" in plan.tools:
            search_text = question + " " + str(run or "")
            with recorder.span("tool.find_similar_incidents", question) as span:
                evidence["incidents"] = self.tools.find_similar_incidents(search_text)
                span["output"] = [item["id"] for item in evidence["incidents"]]
            used.append("find_similar_incidents")

        vuser_request = self._parse_vuser_request(question)
        if vuser_request:
            with recorder.span("tool.estimate_vusers", vuser_request) as span:
                evidence["vusers"] = self.tools.estimate_vusers(**vuser_request)
                span["output"] = evidence["vusers"]
            used.append("estimate_vusers")

        if "draft_change_plan" in plan.tools:
            with recorder.span("tool.draft_change_plan", question) as span:
                evidence["change_plan"] = self.tools.draft_change_plan(question)
                span["output"] = evidence["change_plan"]
            used.append("draft_change_plan")

        return evidence, contexts, used

    @staticmethod
    def _parse_vuser_request(question: str) -> dict[str, float] | None:
        if not re.search(r"vuser|가상\s*사용자|동시\s*사용자", question, re.I):
            return None
        tps_match = re.search(r"([\d.]+)\s*TPS", question, re.I)
        think_match = re.search(r"(?:think\s*time|씽크\s*타임|대기시간)[^\d]*([\d.]+)\s*초", question, re.I)
        response_match = re.search(r"(?:응답시간|response)[^\d]*([\d.]+)\s*초", question, re.I)
        if not tps_match:
            return None
        return {
            "tps": float(tps_match.group(1)),
            "response_sec": float(response_match.group(1)) if response_match else 1.0,
            "think_sec": float(think_match.group(1)) if think_match else 30.0,
        }

    def _offline_answer(self, question: str, route: Route, evidence: dict[str, Any]) -> str:
        if route == Route.ANALYSIS:
            return self._analysis_answer(evidence)
        if route == Route.REPORT:
            return self._report_answer(evidence)
        return self._knowledge_answer(question, evidence)

    @staticmethod
    def _analysis_answer(evidence: dict[str, Any]) -> str:
        run = evidence.get("run", {})
        if "error" in run:
            return (
                f"확인할 수 없습니다: {run['error']} "
                "추가 정보 요청: 예를 들어 `PAY-LOAD-001 결과를 분석해줘`처럼 유효한 테스트 ID를 포함해 주세요."
            )
        kpis = evidence.get("kpis", {})
        lines = [
            f"종합 판단: {kpis.get('verdict', '추가 확인 필요')}",
            "",
            f"목표 {run['target_tps']} TPS 대비 {run['actual_tps']} TPS로 "
            f"달성률 {kpis.get('achievement_pct', 0)}%입니다. 평균/P95 응답시간은 "
            f"{run['avg_response_sec']}초/{run['p95_response_sec']}초, 오류율은 "
            f"{run['error_rate_pct']}%, WAS CPU {run['was_cpu_pct']}%입니다.",
            "",
            "관측 사실",
        ]
        lines.extend(f"- {item}" for item in run.get("observations", []))
        if run.get("db_pool_pct", 0) >= 90 and run.get("was_cpu_pct", 100) < 70:
            lines += [
                "",
                "가설",
                "- WAS CPU 여유와 DB Connection Pool 포화가 함께 보여 DB 연결 대기 또는 Slow SQL 병목 가능성이 가장 높습니다.",
                "",
                "확인 순서",
                "- DB Active Session과 Wait Event 확인",
                "- Connection Pool 대기시간과 최대값 확인",
                "- Slow SQL 실행계획 확인 후 동일 부하 재측정",
            ]
        if run.get("test_type") == "availability":
            lines += [
                "",
                "가설",
                "- 복구 인스턴스 Warm-up 전 L4 재편입 또는 Keep-Alive 편중 가능성이 있습니다.",
                "",
                "확인 순서",
                "- L4 헬스체크와 Ready 조건 확인",
                "- 신규/기존 연결 분포와 Warm-up 완료 시각 비교",
                "- JMeter 120초 타임아웃 영향을 분리해 재판정",
            ]
        if run.get("test_type") == "max_load" and run.get("service") == "sales-support":
            lines += [
                "",
                "추정 한계",
                "- 2대 1000 TPS는 추세 기반 추정이며 실측 아님. 운영 확정 전 추가 검증이 필요합니다.",
            ]
        incidents = evidence.get("incidents", [])
        if incidents:
            top = incidents[0]
            lines += ["", f"유사 사례: {top['id']} — {top['cause']}"]
        return "\n".join(lines)

    @staticmethod
    def _report_answer(evidence: dict[str, Any]) -> str:
        run = evidence.get("run", {})
        if "error" in run:
            return "보고서를 만들 테스트 ID가 필요합니다. 예: `KDB-LOAD-001 임원 보고용으로 요약해줘`."
        kpis = evidence.get("kpis", {})
        return "\n".join(
            [
                f"1. 종합 판정은 {kpis.get('verdict', '추가 확인 필요')}입니다.",
                f"2. 목표 {run['target_tps']} TPS 대비 {run['actual_tps']} TPS를 확인해 달성률 {kpis.get('achievement_pct', 0)}%입니다.",
                f"3. 평균/P95/최대 응답시간은 {run['avg_response_sec']}초/{run['p95_response_sec']}초/{run['max_response_sec']}초이며 오류율은 {run['error_rate_pct']}%입니다.",
                f"4. WAS CPU {run['was_cpu_pct']}%이며 테스트 조건은 ‘{run.get('environment_note', '별도 사항 없음')}’입니다.",
                "5. 운영 전 실패 항목을 보완하고 동일 조건 재검증 및 결과 추적을 권고합니다.",
            ]
        )

    @staticmethod
    def _knowledge_answer(question: str, evidence: dict[str, Any]) -> str:
        if "vusers" in evidence:
            item = evidence["vusers"]
            return (
                "VUser = TPS × (평균 응답시간 + Think Time) 공식을 적용합니다. "
                f"{item['tps']} TPS × ({item['response_sec']}초 + {item['think_sec']}초) = "
                f"약 {item['required_vusers']} VUser가 필요합니다. "
                "계산 근거: 결과값은 소수점 첫째 자리에서 반올림한 정수입니다. "
                "실제 테스트에서는 네트워크와 부하 발생기 여유를 추가 확인하세요."
            )
        lowered = question.lower()
        if any(word in lowered for word in ("양자 gpu", "점성술", "로또 번호", "날씨 예보")):
            return "제공된 Performance Station 문서에서 근거를 확인할 수 없습니다. 성능검증 범위의 테스트 ID나 지표를 더 구체적으로 알려주세요."
        if "cpu" in lowered and any(word in lowered for word in ("40", "낮", "안 올라", "정체")):
            return (
                "CPU가 약 40%인데 TPS가 정체되면 WAS 증설을 바로 결론내리기보다 외부 병목을 확인해야 합니다. "
                "우선순위는 ① 부하 발생기와 VUser ② DB Connection Pool·Wait Event·Slow SQL "
                "③ 외부 연계 지연·Circuit Breaker ④ Thread Pool·락입니다. 관측 사실과 가설을 분리해 확인하세요."
            )
        if any(word in lowered for word in ("가용성", "was1", "failover", "장애 전환")):
            return (
                "가용성 테스트는 정상 기준선 저장 → 한 인스턴스 장애 → L4 제외·전환 확인 → 생존 서버 관측 → "
                "복구·Warm-up → 재편입 순서로 수행합니다. TPS 회복 시간, 오류율, P95, 세션 유실을 함께 판정하고 "
                "복구 시 급증은 L4 헬스체크·Keep-Alive·Warm-up을 확인합니다."
            )
        if any(word in lowered for word in ("목표 tps", "tps 산정", "처리량 산정")):
            return (
                "목표 TPS는 업무량 × 피크 집중률 × 업무 비중에 여유율을 더해 산정합니다. "
                "산정 근거와 피크 시간대를 기록하고, 응답시간·오류율·CPU 기준을 함께 정의해야 합니다. "
                "VUser 환산은 `TPS × (응답시간 + Think Time)`을 사용합니다."
            )
        if any(word in lowered for word in ("안정성", "8시간", "장시간")):
            return (
                "안정성 테스트는 목표 부하의 70% 이상을 8시간 유지하며 응답시간 추세, 오류율, Heap·GC, "
                "Thread와 Connection Pool 누적 변화를 확인합니다. 순간값보다 시간에 따른 누수와 성능 저하가 핵심입니다."
            )
        docs = evidence.get("documents", [])
        if not docs or docs[0].get("score", 0) < 0.02:
            return "제공된 Performance Station 문서에서 근거를 확인할 수 없습니다. 테스트 ID나 지표를 더 구체적으로 알려주세요."
        top = docs[0]
        snippet = " ".join(line.strip() for line in top["text"].splitlines() if line.strip())
        return f"{snippet[:500]}\n\n근거 문서: {top['source']}"

    @staticmethod
    def _change_answer(evidence: dict[str, Any]) -> str:
        plan = evidence.get("change_plan", {})
        return "\n".join(
            [
                "운영 변경은 자동 실행하지 않습니다. 승인 가능한 변경 계획 초안을 만들었습니다.",
                f"- 영향: {plan.get('impact', '확인 필요')}",
                f"- 사전 점검: {', '.join(plan.get('prechecks', []))}",
                f"- 롤백: {plan.get('rollback', '기존 설정 복원')}",
                "승인 전에는 어떤 변경도 수행되지 않습니다.",
            ]
        )


def build_agent(profile: str = "round2") -> PerformanceStationAgent:
    return PerformanceStationAgent(profile=profile)
