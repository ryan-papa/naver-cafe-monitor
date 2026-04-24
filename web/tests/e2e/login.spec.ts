import { test, expect } from '@playwright/test';
import { runA11y } from './fixtures';

test.describe('/login page', () => {
	test('renders brand, title, fields, and submit button', async ({ page }) => {
		await page.goto('/login');

		await expect(page.locator('.auth__logo')).toHaveText('NC');
		await expect(page.locator('.auth__brand-title')).toHaveText('Naver Cafe Monitor');
		await expect(page.locator('.auth__brand-sub')).toContainText('Admin');
		await expect(page.locator('#login-title')).toHaveText('로그인');

		await expect(page.locator('#email')).toBeVisible();
		await expect(page.locator('#password')).toBeVisible();
		await expect(page.locator('#submit')).toBeVisible();

		// TOTP 스텝은 최초에는 숨김 상태 (HTML `hidden` 속성)
		await expect(page.locator('#totp-step')).toHaveAttribute('hidden', /.*/);
	});

	test('empty submit triggers native validation (email is required)', async ({ page }) => {
		await page.goto('/login');
		await page.locator('#submit').click();

		// HTML5 validation 이 걸리면 포커스가 첫 invalid 필드로 이동
		const emailInvalid = await page.locator('#email').evaluate(
			(el: HTMLInputElement) => !el.validity.valid,
		);
		expect(emailInvalid).toBe(true);
	});

	test('accessibility — /login is free of critical/serious violations', async ({ page }) => {
		await page.goto('/login');
		await runA11y(page);
	});
});
