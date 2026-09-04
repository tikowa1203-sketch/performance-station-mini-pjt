# round2 RAGAS 평가 리포트

> 이 리포트는 실제 AWS Bedrock 호출로 생성한 결과입니다(USE_BEDROCK=true). RAGAS 지표는 자체 Judge 기반 근사치이며, RAGAS 라이브러리로 재계산하려면 `ragas_evaluate.py`를 실행합니다.

## 요약

- 인-아웃 세트 통과: **24/28 (85.7%)**
- context_precision: **0.964**
- context_recall: **0.786**
- faithfulness: **0.868**
- answer_relevancy: **0.887**

## 케이스별 결과

| ID | 분류 | 통과 | Trait | Tool | 금지어 | 누락 Trait |
|---:|---|:---:|---:|:---:|:---:|---|
| 1 | positive | PASS | 0.75 | Y | Y | 응답시간과 오류율 함께 판정 |
| 2 | positive | PASS | 1.00 | Y | Y | - |
| 3 | positive | PASS | 0.75 | Y | Y | FAIL |
| 4 | positive | PASS | 1.00 | Y | Y | - |
| 5 | positive | PASS | 1.00 | Y | Y | - |
| 6 | positive | PASS | 0.75 | Y | Y | 테스트 조건 |
| 7 | positive | PASS | 0.75 | Y | Y | Heap |
| 8 | positive | PASS | 1.00 | Y | Y | - |
| 9 | negative | FAIL | 0.50 | Y | Y | 추가 정보 요청 |
| 10 | negative | FAIL | 0.00 | Y | Y | 근거를 확인할 수 없음, 성능검증 범위 |
| 11 | guardrail | PASS | 1.00 | Y | Y | - |
| 12 | guardrail | PASS | 1.00 | Y | Y | - |
| 13 | edge | PASS | 1.00 | Y | Y | - |
| 14 | edge | PASS | 1.00 | Y | Y | - |
| 15 | edge | FAIL | 0.50 | Y | Y | 부하 발생기, 관측 사실과 가설 |
| 16 | edge | PASS | 1.00 | Y | Y | - |
| 17 | edge | PASS | 1.00 | Y | Y | - |
| 18 | negative | PASS | 0.67 | Y | Y | 8시간 |
| 19 | guardrail | PASS | 1.00 | Y | Y | - |
| 20 | guardrail | PASS | 1.00 | Y | Y | - |
| 21 | positive | PASS | 1.00 | Y | Y | - |
| 22 | positive | PASS | 0.75 | Y | Y | 저장 |
| 23 | positive | PASS | 1.00 | Y | Y | - |
| 24 | positive | PASS | 1.00 | Y | Y | - |
| 25 | positive | PASS | 1.00 | Y | Y | - |
| 26 | positive | PASS | 1.00 | Y | Y | - |
| 27 | positive | FAIL | 0.25 | Y | Y | 오류 메시지, Load Generator, 조치 방법 |
| 28 | positive | PASS | 0.75 | Y | Y | SLA |

## 해석

- `round1`: 키워드 검색과 최소 도구만 사용한 기준선입니다.
- `round2`: 쿼리 확장·하이브리드 검색·KPI 계산·유사 장애 비교·가드레일을 결합한 개선 버전입니다.
- 프록시 지표는 빠른 회귀 테스트용이며 제출 직전 AWS 자격증명 환경에서 실제 RAGAS를 실행해야 합니다.
