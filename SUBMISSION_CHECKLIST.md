# 제출 체크리스트

- [ ] `SERVICE.md`의 사용자·문제·가치·확장 관점 최종 검토
- [ ] `evaluation/test_queries.csv` 20건과 실제 데모 질문 일치 확인
- [ ] `python evaluation/evaluate.py --profile all` 재실행
- [ ] AWS 환경에서 `USE_BEDROCK=true python evaluation/ragas_evaluate.py` 실행 후 결과 반영
- [ ] `pytest -q` 통과
- [ ] `docker build -t performance-station-ai .` 성공
- [ ] `.env`, 자격증명, 실제 고객 데이터, `traces.jsonl` 제외 확인
- [ ] ZIP 내부 최상위 폴더가 `mini-pjt_김명연/`인지 확인
- [ ] ZIP 100MB 이하 확인
- [ ] 과제 원문의 마감 시각이 14:00/15:00로 불일치하므로 강사 최종 공지 확인
- [ ] Google Form 업로드 후 최종 제출본 이름 확인

