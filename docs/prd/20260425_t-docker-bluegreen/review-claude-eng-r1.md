# Eng Review (Claude) — r1

| # | 항목 | 점수 | 근거 |
|:-:|------|:--:|------|
| 1 | 아키텍처 | 8 | Compose 4 서비스·deploy-infra 분리·multi-stage(web). api single-stage·하드닝은 §10.1 MUST-FIX 통제 |
| 2 | 확장성 | 9 | mf 공유·INFRA_SWITCH 단계 전환·cron 범위 밖. concurrency 그룹 PRD vs deploy.yml 불일치 |
| 3 | 보안 | 7 | sops·SSL ro·.dockerignore. SSL default·키파일 패턴·actor 게이트 미반영 (모두 §10.1) |
| 4 | 성능 | 8 | RSS 추산·mem_limit. web prune·on-failure:3 미반영 |
| 5 | 운영성 | 9 | 가드 7종·헬스·롤백·MySQL grep·OAuth·E2E·dry-run |

**종합**: 평균 8.2 / 최저 7 / **통과**

## High/Critical 잔여 ([7] dev 처리)

| # | 등급 | 항목 |
|:-:|:--:|------|
| A | Critical | compose `MYSQL_SSL_CERT_DIR_HOST` default 제거 (§10.1 #1) |
| B | High | .dockerignore `**/*.pem`, `**/*.pk8`, `**/*.key`, `**/.ssh`, `**/id_rsa*` 추가 (§10.1 #5) |
| C | High | deploy.yml concurrency 그룹 `museum-eepp-shared-host` 로 mf 와 통일 (§8 #1 정합) |
