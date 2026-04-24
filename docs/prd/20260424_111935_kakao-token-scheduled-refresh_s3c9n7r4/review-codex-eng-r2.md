# Codex 엔지니어링 재리뷰 결과 (r2 개정본 대상)

**일시:** 2026-04-24
**실행:** `codex review` (foreground, 2회차 — r1에서 지적 3건 반영 후 개정본 대상)

## 지적 사항

### [P1] F-29 파일 락 검증을 스레드 테스트로 대체 금지
- `fcntl.flock` 은 같은 프로세스 내 스레드 2개로 검증하면 프로세스 간 경쟁 조건을 재현하지 못함
- 실제 배포 환경(refresh cron 프로세스 + batch 프로세스)의 경합을 검증하려면 **독립 프로세스 2개** 를 기동해야 함

## 반영

- F-29 AC 수정: `multiprocessing.Process` 또는 `subprocess` 사용 명시, 교차 시나리오(refresh + mark_alert_sent) 구체화
- 테스트 전략 테이블 수정: 레벨을 "단위·프로세스간" 으로 변경, threading 기반 검증 명시적 금지

## 결론

High 1건 반영 완료. 엔지니어링 리뷰 단계 종료.
