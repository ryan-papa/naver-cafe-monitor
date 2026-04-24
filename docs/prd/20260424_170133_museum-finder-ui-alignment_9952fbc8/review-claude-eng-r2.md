# 엔지니어링 리뷰 r2

독립 서브에이전트 리뷰 — 메인 에이전트 셀프 채점 아님. r1 피드백 반영 후 업데이트된 PRD(r2)를 **완전히 새로** 채점.

## 점수 테이블

| 항목 | 점수 | 근거 |
|------|------|------|
| 요구사항 명확성 | 9/10 | F-01~F-25가 Must/Should/Could로 분류되고 프리미티브 8종이 F-04a~F-04h로 분해되어 props·variant·AC가 표로 명시됨. F-03 폰트 스코프가 `/admin/* + /login + /signup` 로 명시적. F-10에 쿨다운 정책(성공 시만 30초) 본문화. F-22에서 Bootstrap 제거 + Icon.astro 이관 결정이 확정됨. 남은 작은 흠: F-14 리다이렉트 엔트리 2건만 규정되어 있고 과거 `/posts` 같은 레거시 경로는 "해당 없음"을 명시적으로 적어두면 더 명확. |
| 기술적 실현가능성 | 8/10 | 8-A 섹션에서 바닐라 JS island 패턴을 4가지 유형(순수 마크업/페이지 로컬 script/독립 TS 모듈/data-attribute 훅)으로 결정하고 상태 공유(모듈 스코프 + CustomEvent), 포커스 트랩(`focus-trap` 4KB), 쿨다운(`localStorage` 키 규약)을 기술함. oklch 브라우저 지원 범위(Chrome ≥111, Safari ≥15.4, Firefox ≥113)가 가정 표와 NFR 호환성에 이중 명시. Bootstrap 전역 제거 + bootstrap-icons → Icon.astro 이관 확정. 미세한 리스크: F-04c Select가 native `<select>` 기반인지 커스텀 listbox인지 한 문장 안에서 모호("native select 사용 시 브라우저 기본 동작")—구현 시 결정 필요하나 AC로 추적 가능. |
| 범위·공수 적정성 | 8/10 | 공수 M→L 상향을 11절에서 명시적으로 재평가함. 숨겨진 작업이 F-19(Playwright 설치·config)·F-20(axe 통합)·F-21(CI web 잡)·F-22(Bootstrap 제거)·F-23(프리미티브 단위 E2E)·F-24(리다이렉트 E2E)·F-25(육안 검증 체크리스트)로 전부 드러남. 스코프 표에 포함/비포함이 대칭. 다만 "기존 `/` 페이지 내용을 `/admin/posts` 로 이관"이 F-09 문맥에 녹아있으나 별도 F로 존재하지 않음—구현 태스크에서 놓칠 위험은 있으나 F-09 AC로 커버 가능. |
| NFR 충족도 | 9/10 | 8-B 섹션에 성능 측정(Lighthouse 데스크탑 프리셋 + navigation timing), 렌더 목표(TTFB/FCP/LCP), CSP 헤더 값, SRI + `crossorigin="anonymous"`, `astro check` 타입 검증, 빌드 경고 0 목표가 구체화. 관측가능성에서 302 로그와 4xx/5xx 경로 포맷 유지 명시. `font-display: swap` + fallback 스택. CDN 실패 fallback은 "1차 없음, 운영 관찰 후 self-host 전환"이라는 의도적 결정이 명시됨(검증 가능한 선택). 완벽에 가깝고, 굳이 빼자면 CSP `script-src 'unsafe-inline'` 허용이 장기 보안 관점에선 tightening 여지가 있다는 점 정도. |
| 의존성·리스크 | 8/10 | 8-C 롤백 절차가 단계별로 명시(revert → 재빌드 → 재기동 → 200 확인 + 부분 롤백 + 감지 경로). 리스크 표에 CDN 장애·Bootstrap 충돌·Playwright 브라우저 캐시·세션·루프·FOUC가 전부 열거되고 검증 방법 수반. r1에서 지적된 "롤백 섹션 부재", "CDN fallback", "uvicorn 재시작 세션 영향" 3건이 각각 8-C·리스크 표·롤백 3단계로 해소. 남은 흠: self-hosted runner(macOS) vs. PR 단계 `ubuntu-latest` 분기에서 러너 태그 선택을 F-21 본문이 묵시적으로 `ubuntu-latest`로만 전제—공식 CI 정책(PR=ubuntu, 배포=self-hosted)을 한 줄로 확정하면 더 안전. |
| 테스트 가능성 | 8/10 | r1의 치명 지적(인프라 부재)이 F-19·F-20·F-21·F-23·F-24·F-25 6건으로 해소. Playwright Chromium 단일, axe impact level 필터, CI 캐시 키, 트레이스 아티팩트, 프리미티브 단위 AC(Select 키보드·HelpTip aria-describedby·Modal 포커스 트랩), 리다이렉트 302·체인 루프 검증, 육안 체크리스트 9항이 전부 ID로 추적됨. 성공 기준(성공/실패 접을 기준)이 정량화. 개선 여지: (1) 프리미티브 단위 AC(F-23)가 Select/HelpTip/Modal 3종만 명시—Button variant별 포커스 링, Pill tone별 토큰, Input `aria-invalid` 등 표 안 AC는 있으나 E2E 커버 대상에 포함 여부 애매, (2) Lighthouse 점수 측정을 수동으로 할지 CI에 통합할지(`lhci`) 정책 미명시. 테스트 인프라가 실존 가능한 수준으로 올라온 것은 중대한 진전. |
| **평균** | **8.33** | |

## 판정

**통과(Approved)** — 평균 8.33 (≥ 8.0), 각 항목 8 이상으로 최저 7 요건 충족.

## r1 대비 개선 요약

| r1 지적 | r2 반영 여부 | 위치 |
|---------|-------------|------|
| 테스트 인프라 F 추가 | ✓ 반영 | F-19(Playwright 설치·config) · F-20(axe 통합) · F-21(CI web 잡 + 캐시) |
| 바닐라 JS island 패턴 결정 문서화 | ✓ 반영 | 8-A 섹션(4유형 분류 + 상태 공유 + 포커스 트랩 라이브러리 + 쿨다운 저장소) |
| Bootstrap 처리 방침 | ✓ 반영 | F-22(전역 import 제거 + bootstrap-icons → Icon.astro 이관 확정) |
| oklch 브라우저 지원 범위 명시 | ✓ 반영 | 가정 표 + NFR 호환성(Chrome ≥111, Safari ≥15.4, Firefox ≥113) |
| CDN 실패 fallback + CSP/SRI | ✓ 반영 | 8-B 섹션 + 리스크 표(1차 fallback 없음 결정) + NFR 보안 |
| 롤백 절차 | ✓ 반영 | 8-C 섹션(4단계 + 부분 롤백 + 감지) |
| 프리미티브 8종 props·variant AC 표 | ✓ 반영 | 9-2 섹션 F-04a~F-04h (Button/Input/Select/Pill/Icon/DataTable/PageHeader/HelpTip) |
| 공수 재평가 M→L | ✓ 반영 | 11절 기술 스택·제약사항 "공수 재평가 **L** (초기 M에서 상향)" |
| F-03 폰트 스코프 명시 | ✓ 반영 | F-03 "`/admin/* + /login + /signup` (모든 내부 화면)" |

r1의 9개 블로커 지적이 모두 구체적으로 반영됨. 특히 테스트 인프라(F-19~F-21, F-23~F-25) 신설로 테스트 가능성이 6 → 8로 상승하여 최저 항목 컷(7)을 통과.

## 남은 권고 (non-blocking)

1. F-21 CI 러너 태그(`ubuntu-latest` vs `self-hosted`)를 한 줄로 확정.
2. F-04c Select 구현 방침(native `<select>` 유지 vs. 커스텀 listbox) 중 하나로 단정.
3. Lighthouse 접근성 ≥95 측정을 수동 육안인지 `@lhci/cli` CI 자동화인지 한 줄 추가.
4. F-23 프리미티브 단위 AC 범위에 Button·Pill·Input 포커스/상태 assertion 확장 여부 명시.
5. F-14 리다이렉트 대상이 `/`·`/settings/2fa` 2건만임을 명시("그 외 레거시 경로 없음").

위 항목은 모두 구현 단계(`rp-dev`) AC 정제로 충분히 처리 가능하므로 r2 단계 블로커 아님.
