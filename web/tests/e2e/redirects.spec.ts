import { test, expect } from '@playwright/test';

/**
 * 레거시 경로 리다이렉트 검증.
 * - `/` → `/admin` (미들웨어 legacy redirect) → 미인증이라 최종 `/login?next=/admin`
 */
test.describe('legacy redirects', () => {
	test('GET / (unauthenticated) ends up on /login with next=/admin', async ({ page }) => {
		const response = await page.goto('/', { waitUntil: 'domcontentloaded' });
		expect(response).not.toBeNull();
		await expect(page).toHaveURL(/\/login(\?|$)/);
		const url = new URL(page.url());
		expect(url.searchParams.get('next')).toBe('/admin');
	});

	test('GET / issues a 302 to /admin without following', async ({ request }) => {
		const res = await request.get('/', { maxRedirects: 0 });
		expect(res.status()).toBe(302);
		expect(res.headers()['location']).toBe('/admin');
	});

	test('GET /admin/settings/2fa is 404 (route removed)', async ({ request }) => {
		const res = await request.get('/admin/settings/2fa', { maxRedirects: 0 });
		// 미인증 시 미들웨어 가드로 /login 리다이렉트가 먼저 작동할 수 있으므로 둘 다 허용
		expect([302, 404]).toContain(res.status());
		if (res.status() === 302) {
			expect(res.headers()['location']).toMatch(/^\/login/);
		}
	});
});
