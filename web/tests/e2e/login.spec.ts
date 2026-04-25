import { test, expect } from '@playwright/test';

test.describe('/login redirect', () => {
	test('unauthenticated login immediately redirects to Google OAuth entry', async ({ request }) => {
		const res = await request.get('/login', { maxRedirects: 0 });
		expect(res.status()).toBe(302);
		expect(res.headers()['location']).toBe('/oauth2/authorization/google');
	});
});
