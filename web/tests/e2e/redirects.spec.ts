import { test, expect } from '@playwright/test';

/**
 * 레거시 경로 리다이렉트 검증.
 * - `/` → `/admin` (미들웨어 legacy redirect) → 미인증이라 최종 `/login?next=/admin`
 * - `/settings/2fa` → `/admin/settings/2fa` → 미인증이라 `/login?next=/admin/settings/2fa`
 */
test.describe('legacy redirects', () => {
	test('GET / (unauthenticated) ends up on /login with next=/admin', async ({ page }) => {
		const response = await page.goto('/', { waitUntil: 'domcontentloaded' });
		expect(response).not.toBeNull();
		await expect(page).toHaveURL(/\/login(\?|$)/);
		const url = new URL(page.url());
		expect(url.searchParams.get('next')).toBe('/admin');
	});

	test('GET /settings/2fa (unauthenticated) ends up on /login with next=/admin/settings/2fa', async ({
		page,
	}) => {
		await page.goto('/settings/2fa', { waitUntil: 'domcontentloaded' });
		await expect(page).toHaveURL(/\/login(\?|$)/);
		const url = new URL(page.url());
		expect(url.searchParams.get('next')).toBe('/admin/settings/2fa');
	});

	test('GET / issues a 302 to /admin without following', async ({ request }) => {
		const res = await request.get('/', { maxRedirects: 0 });
		expect(res.status()).toBe(302);
		expect(res.headers()['location']).toBe('/admin');
	});

	test('GET /settings/2fa issues a 302 to /admin/settings/2fa without following', async ({
		request,
	}) => {
		const res = await request.get('/settings/2fa', { maxRedirects: 0 });
		expect(res.status()).toBe(302);
		expect(res.headers()['location']).toBe('/admin/settings/2fa');
	});
});
