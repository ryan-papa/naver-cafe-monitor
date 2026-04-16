> 이 문서는 프로젝트 로컬 규칙이며 최우선 적용된다.
> **⛔ 세션 시작 시 `../../CLAUDE.md`를 반드시 Read로 읽고 적용할 것.**
> 충돌 시 본 문서(프로젝트)가 우선한다.

# naver-cafe-monitor

## Deployment

| 항목 | 내용 |
|------|------|
| 서버 환경 | 로컬 Mac Mini (이 레포가 서버에서 직접 실행됨) |
| API 서버 | uvicorn (`api.src.main:app`, `127.0.0.1:8000`) |
| 배치 | cron 30분 주기 (코드 변경 시 다음 실행에 자동 반영) |
| 프록시 | nginx (재시작 불필요) |

**배포 규칙:**
- PR이 main에 머지되면 자동 배포 진행
- **전제 조건:** uvicorn 프로세스가 실행 중일 때만 배포 (신규 서버 설정 안 함, 기존 환경 업데이트만 수행)
- 배포 절차: `git pull` → 각 컴포넌트별 배포 수행
- 배치(cron)는 별도 조치 없음 (다음 실행 시 자동 반영)

**컴포넌트별 배포:**

| 컴포넌트 | 배포 절차 |
|----------|-----------|
| API | uvicorn 프로세스 재시작 (`kill` + 재실행) |
| 프론트엔드 | `cd web && npm run build && cp -r dist/* /opt/homebrew/var/www/naver-cafe-monitoring/` |
| 배치 | 없음 (다음 cron 실행 시 자동 반영) |
