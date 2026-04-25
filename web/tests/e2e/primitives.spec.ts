import { test, expect } from '@playwright/test';

test.describe('login interaction', () => {
	test.beforeEach(async ({ page }) => {
		await page.route(/\/api\/auth\/me$/, (route) =>
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'server_error' }),
			}),
		);
	});

	test('Google login link is keyboard-focusable', async ({ page }) => {
		await page.goto('/login');

		await page.locator('#google-login').focus();
		await expect(page.locator('#google-login')).toBeFocused();
		await expect(page.locator('#google-login')).toHaveAttribute(
			'href',
			'/oauth2/authorization/google',
		);
	});
});
