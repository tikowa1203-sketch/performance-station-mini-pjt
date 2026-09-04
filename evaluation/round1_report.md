# round1 RAGAS 평가 리포트

> 이 리포트는 실제 AWS Bedrock 호출로 생성한 결과입니다(USE_BEDROCK=true). RAGAS 지표는 자체 Judge 기반 근사치이며, RAGAS 라이브러리로 재계산하려면 `ragas_evaluate.py`를 실행합니다.

## 요약

- 인-아웃 세트 통과: **14/28 (50.0%)**
- context_precision: **1.000**
- context_recall: **0.702**
- faithfulness: **0.766**
- answer_relevancy: **0.883**

## 케이스별 결과

| ID | 분류 | 통과 | Trait | Tool | 금지어 | 누락 Trait |
|---:|---|:---:|---:|:---:|:---:|---|
| 1 | positive | PASS | 0.75 | Y | Y | 응답시간과 오류율 함께 판정 |
| 2 | positive | PASS | 1.00 | Y | Y | - |
| 3 | positive | FAIL | 0.25 | N | Y | FAIL, 달성률 74.0%, Slow SQL 확인 |
| 4 | positive | FAIL | 1.00 | N | Y | - |
| 5 | positive | FAIL | 0.50 | N | Y | FAIL, Warm-up |
| 6 | positive | FAIL | 0.75 | N | Y | 달성률 100.0% |
| 7 | positive | PASS | 0.75 | Y | Y | Heap |
| 8 | positive | FAIL | 1.00 | N | Y | - |
| 9 | negative | FAIL | 0.50 | N | Y | 추가 정보 요청 |
| 10 | negative | FAIL | 0.00 | Y | Y | 근거를 확인할 수 없음, 성능검증 범위 |
| 11 | guardrail | PASS | 1.00 | Y | Y | - |
| 12 | guardrail | PASS | 1.00 | Y | Y | - |
| 13 | edge | FAIL | 1.00 | N | Y | - |
| 14 | edge | FAIL | 1.00 | N | Y | - |
| 15 | edge | FAIL | 0.25 | Y | Y | DB Connection Pool, 부하 발생기, 관측 사실과 가설 |
| 16 | edge | FAIL | 0.25 | Y | Y | L4, Keep-Alive, 재편입 |
| 17 | edge | FAIL | 1.00 | N | Y | - |
| 18 | negative | PASS | 0.67 | Y | Y | 8시간 |
| 19 | guardrail | PASS | 1.00 | Y | Y | - |
| 20 | guardrail | PASS | 1.00 | Y | Y | - |
| 21 | positive | PASS | 1.00 | Y | Y | - |
| 22 | positive | FAIL | 0.50 | Y | Y | 참여 사용자, 저장 |
| 23 | positive | PASS | 0.75 | Y | Y | Correlation |
| 24 | positive | PASS | 1.00 | Y | Y | - |
| 25 | positive | PASS | 1.00 | Y | Y | - |
| 26 | positive | PASS | 1.00 | Y | Y | - |
| 27 | positive | FAIL | 0.25 | Y | Y | 오류 메시지, Load Generator, 조치 방법 |
| 28 | positive | PASS | 0.75 | Y | Y | SLA |

## 해석

- `round1`: 키워드 검색과 최소 도구만 사용한 기준선입니다.
- `round2`: 쿼리 확장·하이브리드 검색·KPI 계산·유사 장애 비교·가드레일을 결합한 개선 버전입니다.
- 프록시 지표는 빠른 회귀 테스트용이며 제출 직전 AWS 자격증명 환경에서 실제 RAGAS를 실행해야 합니다.
