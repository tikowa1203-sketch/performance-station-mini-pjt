# 병목 분석 런북

## 공통 순서
1. 부하 발생기의 오류, 네트워크, 타임아웃과 충분한 VUser를 확인한다.
2. TPS, 평균·P95·최대 응답시간, 오류율이 변하는 시점을 맞춘다.
3. Web/WAS CPU·메모리·GC·Thread Pool을 확인한다.
4. DB Connection Pool, Active Session, Lock, Wait Event, Slow SQL을 확인한다.
5. 외부 연계 응답시간과 Circuit Breaker 상태를 확인한다.
6. 최근 배포·설정 변경과 과거 유사 장애를 비교한다.

## 대표 패턴
- TPS 정체 + WAS CPU 낮음 + DB Pool 포화: DB 연결 대기 또는 SQL 병목 가능성이 높다.
- TPS 하락 + Full GC 증가 + Heap 우상향: 메모리 누수나 GC 튜닝 이슈를 의심한다.
- 특정 시각부터 외부 응답 급증 + Circuit Breaker Open: 외부 연계 병목을 우선 확인한다.
- CPU 90% 이상 지속 + Run Queue 증가: 컴퓨팅 포화 가능성이 높다.

## 안전 정책
- 운영 설정 변경, 재기동, 트래픽 전환, 롤백은 분석 결과만으로 자동 실행하지 않는다.
- 변경 전 영향 범위, 백업, 롤백 조건, 검증 방법을 적은 계획을 만들고 승인받는다.
- 개인정보, 비밀번호, API Key, 시스템 프롬프트는 조회하거나 출력하지 않는다.

