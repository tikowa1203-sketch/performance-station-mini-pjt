# 수평 확장 로드맵

현재 구조는 Supervisor가 Specialist Agent와 Tool을 선택하고, 각 기능은 공통 RAG·가드레일·Trace 계층을 공유한다. 새 기능은 기존 Agent의 책임을 키우기보다 새 Agent와 Tool을 옆으로 추가한다.

## 확장 순서

| 버전 | 추가 Agent | 주요 Tool·데이터 | 사용자 가치 |
|---|---|---|---|
| v1.0 현재 | Knowledge·Analysis·Report·Change | 문서, 테스트 JSON, 장애 사례 | 검색·분석·보고·승인 계획 |
| v1.1 | Test Design Agent | 업무량 수집, 시나리오 생성, 부하 모델 | 테스트 계획 자동 설계 |
| v1.2 | Live Monitor Agent | APM·Prometheus·JMeter MCP | 테스트 중 이상 탐지와 중단 권고 |
| v1.3 | Capacity Agent | 추세 DB, 회귀분석, 비용 정보 | 증설 시점·용량·비용 비교 |
| v1.4 | Regression Agent | 버전별 기준선과 배포 이력 | 릴리스 성능 회귀 자동 판정 |
| v1.5 | Governance Agent | 승인·감사·RBAC·정책 | 고객별 안전한 운영 적용 |

## 기능 추가 계약

1. `src/specialists.py`에 새 `SpecialistSpec`을 등록한다.
2. `src/tools.py`에 읽기 전용 Tool부터 추가하고 입력·출력을 Pydantic으로 고정한다.
3. `data/`에 근거 데이터와 출처·갱신일 메타데이터를 넣는다.
4. `evaluation/test_queries.csv`에 positive·negative·edge·guardrail을 추가한다.
5. Trace step 이름을 `agent.<name>` 또는 `tool.<name>`으로 통일한다.
6. 운영 쓰기 작업은 반드시 Change Agent와 HITL을 통과시킨다.

## 우선 구현 추천

다음 Mini PJT에서는 **Test Design Agent**를 먼저 추가하는 것이 좋다. Performance Station의 기존 성능 실행 기능 앞단에 목표 TPS 산정, 업무 비중, VUser, Ramp-up, 성공 기준을 자동 설계하면 현재 분석 기능과 자연스럽게 연결되고 데모 가치도 크다.

