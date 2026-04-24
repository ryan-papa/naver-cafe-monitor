import { test, expect } from '@playwright/test';

/**
 * 루트 접근 플로우 (미인증 시나리오).
 * 302 체이닝: `/` → `/admin` → `/login?next=/admin`
 */
test('unauthenticated root flow redirects through /admin to /login', async ({ request }) => {
	// 1단계: / → /admin
	const first = await request.get('/', { maxRedirects: 0 });
	expect(first.status()).toBe(302);
	expect(first.headers()['location']).toBe('/admin');

	// 2단계: /admin → /login?next=/admin
	const second = await request.get('/admin', { maxRedirects: 0 });
	expect(second.status()).toBe(302);
	const loc = second.headers()['location'] ?? '';
	expect(loc).toMatch(/^\/login\?/);
	expect(loc).toContain('next=%2Fadmin');
});
