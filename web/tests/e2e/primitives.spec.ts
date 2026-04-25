import { test, expect } from '@playwright/test';

test.describe('login route interaction', () => {
	test('does not render an intermediate choice screen', async ({ request }) => {
		const res = await request.get('/login', { maxRedirects: 0 });
		expect(res.status()).toBe(302);
		expect(res.headers()['location']).toBe('/oauth2/authorization/google');
	});
});
