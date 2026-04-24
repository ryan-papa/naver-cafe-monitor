import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 설정 — Astro SSR 프런트 E2E·접근성 검증용.
 *
 * 주의: 로그인·API 호출이 필요한 테스트는 백엔드 모킹이 필요하므로,
 * 본 설정에서는 정적 경로·리다이렉트·UI 인터랙션 위주의 테스트만 커버한다.
 * 내부 API 베이스는 테스트 환경에서 빈 값으로 두어 `fetchMe`가 null을 반환하더라도
 * 미들웨어가 /login 리다이렉트로 떨어지도록 둔다.
 */
export default defineConfig({
	testDir: './tests/e2e',
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 1 : 0,
	workers: process.env.CI ? 1 : undefined,
	reporter: [['html', { open: 'never' }], ['list']],
	use: {
		baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4321',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] },
		},
	],
	webServer: {
		command: 'npm run build && node dist/server/entry.mjs',
		port: 4321,
		reuseExistingServer: !process.env.CI,
		timeout: 120_000,
		env: {
			HOST: '127.0.0.1',
			PORT: '4321',
			// 실제 API 없이 구동 — 미들웨어가 보호 경로에서 /login 으로 리다이렉트하도록 유지.
			INTERNAL_API_BASE: process.env.INTERNAL_API_BASE || 'http://127.0.0.1:65535',
		},
	},
});
