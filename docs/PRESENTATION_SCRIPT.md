
---

## 0. 한 문장 소개

"이 프로젝트는 Performance Station이라는 사내 성능테스트 도구의 사용법과 성능 테스트 지식을 자연어로 안내하고, 필요하면 계산·테스트 조회·병목 분석·보고까지 만들어주는 Agentic RAG Copilot입니다. Supervisor가 질문 의도를 분류해서 4개의 전문 Agent와 6개의 Tool 중 필요한 것만 골라 쓰는 구조로 만들었습니다."

---

## 1. 프로젝트 목적

"먼저 왜 이 프로젝트를 이렇게 설계했는지 말씀드리겠습니다.

- 문제: Performance Station 사용법과 성능 테스트 지식이 사용자 가이드, 교육자료, 담당자 경험에 분산되어 있어서, 신규 사용자는 테스트 준비·실행·결과 확인 과정에서 숙련자에게 반복적으로 문의하게 됩니다.
- 핵심 가치: 자연어 질문 한 번으로 (1) 사용법 안내, (2) VUser 계산, (3) 테스트 결과 조회, (4) 병목 분석, (5) 임원 보고까지 이어지는 흐름을 지원합니다.
- 확장 전략: `SERVICE.md`에 1단계(사용 지원)→2단계(분석 지원)→3단계(업무 자동화) 순서로 로드맵을 정의해뒀고, 실제 코드는 이미 2·3단계에 해당하는 Analysis/Report/Change Agent까지 구현이 앞서 나가 있는 상태입니다."

[여기서 SERVICE.md의 '단계별 확장 방향' 표를 화면에 띄워서 보여줍니다]

---

## 2. 폴더 구조

"프로젝트 구조를 코드보다 먼저 보여드리겠습니다."

```text
mini-pjt_00/
├── SERVICE.md              # 서비스 기획서 — 문제, 가치, 정책, 성공 기준
├── README.md                # 아키텍처, 실행 방법, 패턴 매핑, 회고
├── src/                      # 실제 동작하는 코드
│   ├── api.py                #   FastAPI 엔드포인트 (/query, /approve)
│   ├── agent.py               #   메인 오케스트레이션 (Guardrail→Route→Tool→답변)
│   ├── agents.py              #   Supervisor(라우팅), BedrockSynthesizer(답변 합성)
│   ├── specialists.py          #   Knowledge/Analysis/Report/Change Agent 정의
│   ├── tools.py                #   6개 도메인 Tool (검색/계산/조회)
│   ├── retriever.py            #   하이브리드 RAG 검색기
│   ├── guardrails.py           #   인젝션·민감정보·PII·위험행동 방어
│   ├── memory.py, tracing.py    #   대화 요약, 단계별 Trace 기록
│   ├── react_agent.py          #   LangGraph ReAct 패턴 데모
│   └── mcp_server.py           #   MCP(stdio) 서버 데모
├── data/                     # RAG 지식베이스 + 합성 테스트 데이터
│   ├── 01_getting_started.md ~ 07_troubleshooting_faq.md   # 사용법 가이드 7종
│   ├── performance_test_standard.md, *_runbook.md 등        # 성능 표준/런북
│   └── test_runs.json, incidents.json                       # 합성 테스트 결과·장애 사례
├── evaluation/               # 품질 검증
│   ├── test_queries.csv       #   27개 인-아웃 평가 케이스
│   ├── evaluate.py             #   자체 Judge 기반 회귀 평가
│   └── ragas_evaluate.py       #   실제 Bedrock+RAGAS 평가
├── tests/                    # pytest 회귀 테스트
└── docs/                     # 로드맵·데모 시나리오·발표 스크립트
```

"핵심만 짚으면, `src/`가 실제 서비스 로직이고, `data/`가 RAG의 근거 문서이며, `evaluation/`이 이 프로젝트가 실제로 잘 동작하는지 수치로 증명하는 부분입니다. 이 세 개가 서로 맞물려 있다는 게 이 프로젝트에서 가장 신경 쓴 부분입니다."

---

## 3. 어떻게 구현했는지 (3~4분)

### 3-1. 전체 흐름

"사용자 질문이 들어오면 다음 순서로 처리됩니다."

```
사용자 질문
 → ① Guardrail (인젝션/민감정보 차단, PII 마스킹)
 → ② Supervisor 라우팅 (Knowledge/Analysis/Report/Change 중 선택)
 → ③ 해당 Agent의 Tool 실행 (문서 검색·테스트 조회·KPI 계산·유사사례 검색 등)
 → ④ 답변 합성 (Bedrock 구조화 출력) + Trace 기록
 → ⑤ 위험 변경이면 실행하지 않고 승인 대기(HITL)
```

[여기서 README.md의 mermaid 아키텍처 다이어그램을 보여줍니다]

### 3-2. RAG는 왜 하이브리드로 만들었나

"임베딩 모델 없이도 동작하도록, BM25 키워드 검색과 로컬 코사인 유사도를 RRF(Reciprocal Rank Fusion)로 결합하고, 마지막에 쿼리-청크 토큰 커버리지와 문서 제목 매칭으로 한 번 더 재랭킹합니다. 문서는 마크다운 헤딩 단위로 잘라 청크로 만드는데, 헤딩만 있고 본문이 거의 없는 얇은 청크는 다음 절에 합쳐서 노이즈를 줄였습니다."

### 3-3. Tool과 Agent 계약

"`specialists.py`에 Route별로 어떤 Agent가 어떤 Tool을 기본으로 쓰는지 계약을 고정해뒀습니다. 예를 들어 Analysis Agent는 테스트 조회+KPI 계산+유사 장애 검색+문서 검색을 항상 함께 씁니다. LLM이 라우팅과 Tool 선택을 하긴 하지만, 최종적으로는 이 Specialist 계약이 항상 포함되도록 만들어서, LLM이 일부 Tool만 고르거나 이름을 잘못 짓더라도 필요한 근거 수집이 누락되지 않게 했습니다."

### 3-4. 안전장치 (Guardrail + HITL)

"프롬프트 인젝션, 자격증명/민감정보 요청은 입력 단계에서 차단하고, 전화번호 같은 PII는 출력에서 `[PHONE]`으로 마스킹합니다. 운영 변경처럼 위험한 요청은 절대 바로 실행하지 않고 영향·사전점검·롤백 계획만 만든 뒤 `approval_required` 상태로 멈춥니다. 승인해도 실제로는 아무것도 실행하지 않는 Dry-run입니다."

### 3-5. 12개 패턴 적용

"이번 교육 과정에서 배운 패턴들을 하나의 프로젝트에 실제로 녹였습니다 — LCEL·구조화 출력, ReAct, RAG, 다중 Tool, MCP, 가드레일, HITL, 미들웨어, Multi-Agent Supervisor, Plan-Execute·메모리, Observability(Trace), RAGAS 평가까지 12개입니다. 표는 README에 정리해뒀습니다."

---

## 4. 라이브 데모 시나리오 (2분)

"짧게 4가지 질문으로 흐름을 보여드리겠습니다."

1. `104 TPS에 응답시간 1초 Think Time 30초면 VUser가 몇 명 필요해?`
   → 문서 검색 + 계산 Tool을 함께 쓰고, 계산식과 반올림 기준을 답변에 명시합니다.
2. `PAY-LOAD-001의 병목 원인을 분석해줘`
   → 목표 달성률, WAS CPU, DB Pool 상태, 과거 유사 사례를 결합하되 원인을 확정하지 않고 가설/확인 순서로 분리합니다.
3. `KDB-LOAD-001 결과를 임원 보고용 5문장으로 요약해줘`
   → 같은 데이터를 목적에 맞게 결론 우선 보고로 바꿉니다.
4. `운영 DB Connection Pool을 300으로 변경해줘`
   → 바로 실행하지 않고 변경 계획만 만든 뒤 승인 대기 상태로 멈춥니다.

[`docs/DEMO_SCENARIO.md`에 시간 배분까지 정리되어 있습니다]

---

## 5. 어떻게 검증했는지 (1.5~2분)

"이 프로젝트에서 가장 강조하고 싶은 부분입니다. 두 단계로 검증했습니다.

1단계 — 오프라인 회귀 평가(`evaluate.py`): AWS 자격증명 없이도 27개 인-아웃 케이스를 결정적으로 반복 실행해서 회귀를 빠르게 잡습니다.

2단계 — 실제 Bedrock 평가: `.env`에 실제 AWS 자격증명을 넣고 같은 27개 케이스를 실제 LLM으로 돌렸습니다. 그런데 이 단계에서 오프라인 평가로는 절대 못 잡는 버그를 두 개 실제로 발견했습니다.

- Tool 이름 환각: Supervisor가 route는 정확히 분류했지만, 실제 LLM이 `retrieve_docs` 같은 실제 Tool 이름 대신 `performance_analyzer`, `manual_search`처럼 그럴듯하지만 존재하지 않는 이름을 만들어내서, 아무 Tool도 실행되지 않는 문제였습니다. 프롬프트에 정확한 Tool 이름 목록을 명시하고, 유효하지 않은 이름은 걸러내고 Specialist 기본 Tool로 대체하도록 방어 코드를 추가해서 고쳤습니다.
- 가드레일 오탐: 로그인 방법을 설명하는 정상 문서에 '비밀번호'라는 단어가 들어있다는 이유만으로, 출력 단계 가드레일이 전체 답변을 '민감정보라 제공할 수 없다'며 차단해버리는 문제였습니다. 이건 실제 사용법 문서를 채워 넣고 실제 LLM으로 돌려봤기 때문에 발견할 수 있었습니다.

이 두 가지는 오프라인 목(mock) 평가만으로는 절대 드러나지 않았을 문제라서, '실제 자격증명으로 한 번은 꼭 돌려봐야 한다'는 걸 직접 체감했습니다."

[여기서 `evaluation/round2_report.md`의 최신 통과율 표를 보여줍니다]

---

## 6. 앞으로의 확장 (30초~1분)

"`docs/HORIZONTAL_ROADMAP.md`에 다음 확장 순서를 정리해뒀습니다. 새 기능은 기존 Agent의 책임을 키우기보다 `specialists.py`에 새 Agent, `tools.py`에 새 Tool을 옆으로 추가하는 방식입니다. 다음 단계로는 테스트 계획을 자동 설계하는 Test Design Agent 추가를 우선순위로 잡고 있습니다."

---

## 예상 질문 대비 Q&A

Q. RAG에 임베딩 모델을 안 쓴 이유는?
A. 자격증명 없이도 재현 가능한 오프라인 회귀 평가를 만들기 위해서입니다. BM25+로컬 코사인 유사도로 1차 후보를 뽑고 RRF로 결합한 뒤, 실제 운영에서는 Bedrock 기반 LLM 합성 단계에서 최종 품질을 보정합니다.

Q. LLM이 매번 다른 답을 하면 평가는 어떻게 하나?
A. 오프라인 프록시 평가로 빠른 회귀 테스트를 하고, 제출 전에는 실제 Bedrock으로 한 번 더 실측합니다. 이번에 그 실측 과정에서 실제 버그 두 개를 찾아 고쳤습니다.

Q. 승인(HITL) 이후에는 실제로 뭐가 바뀌나?
A. 아무것도 바뀌지 않습니다. 교육용 프로젝트라 운영 시스템에 연결되어 있지 않고, 승인 후에도 Dry-run 상태(`approved_dry_run`)로만 응답합니다.
