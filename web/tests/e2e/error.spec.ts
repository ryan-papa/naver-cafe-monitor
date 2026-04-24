import { test, expect } from '@playwright/test';
import { runA11y } from './fixtures';

/**
 * 에러 페이지 렌더링·접근성 검증.
 * public-paths 에 포함되어 있으므로 인증 없이 접근 가능.
 */
const pages: Array<{ path: string; code: string }> = [
	{ path: '/error/404', code: '404' },
	{ path: '/error/500', code: '500' },
];

for (const { path, code } of pages) {
	test.describe(`${path}`, () => {
		test(`renders code ${code}`, async ({ page }) => {
			await page.goto(path);
			await expect(page.locator('body')).toContainText(code);
			// 공통 "대시보드로 돌아가기" 링크가 있어야 함
			await expect(page.getByRole('link', { name: /대시보드|돌아가기|홈/ })).toBeVisible();
		});

		test('is free of critical/serious a11y violations', async ({ page }) => {
			await page.goto(path);
			await runA11y(page);
		});
	});
}
