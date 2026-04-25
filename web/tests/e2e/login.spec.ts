import { test, expect } from '@playwright/test';
import { runA11y } from './fixtures';

test.describe('/login page', () => {
	test.beforeEach(async ({ page }) => {
		await page.route(/\/api\/auth\/me$/, (route) =>
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'server_error' }),
			}),
		);
	});

	test('renders brand, title, and Google login link', async ({ page }) => {
		await page.goto('/login');

		await expect(page.locator('.auth__logo')).toHaveText('NC');
		await expect(page.locator('.auth__brand-title')).toHaveText('Naver Cafe Monitor');
		await expect(page.locator('.auth__brand-sub')).toContainText('Admin');
		await expect(page.locator('#login-title')).toHaveText('로그인');

		await expect(page.locator('#google-login')).toBeVisible();
		await expect(page.locator('#google-login')).toHaveAttribute(
			'href',
			'/oauth2/authorization/google',
		);

		await expect(page.locator('#email')).toHaveCount(0);
		await expect(page.locator('#password')).toHaveCount(0);
		await expect(page.locator('#totp')).toHaveCount(0);
		await expect(page.locator('#totp-step')).toHaveCount(0);
	});

	test('401 from me redirects to Google OAuth', async ({ page }) => {
		await page.unroute(/\/api\/auth\/me$/);
		await page.route(/\/api\/auth\/me$/, (route) => route.fulfill({ status: 401 }));
		const oauth = { called: false };
		await page.route(/\/oauth2\/authorization\/google$/, (route) => {
			oauth.called = true;
			route.fulfill({ status: 200, contentType: 'text/html', body: '<html>oauth</html>' });
		});
		await page.goto('/login');
		await expect.poll(() => oauth.called, { timeout: 10_000 }).toBe(true);
	});

	test('accessibility — /login is free of critical/serious violations', async ({ page }) => {
		await page.goto('/login');
		await runA11y(page);
	});
});
