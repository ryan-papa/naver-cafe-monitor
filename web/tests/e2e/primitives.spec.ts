import { test, expect } from '@playwright/test';

/**
 * 프리미티브(Button·Input) 단위 AC E2E.
 *
 * 전용 스토리·데모 페이지가 없으므로 /login 에 노출된 프리미티브로 간접 검증한다.
 * Select 키보드 네비·HelpTip ESC 시나리오는 인증 벽이 있는 /admin/** 에서만
 * 노출되므로 본 배치에서는 커버 불가 — 후속 배치에서 테스트용 페이지 도입 시 추가.
 */
test.describe('primitives on /login', () => {
	test('Button activates with keyboard Enter (Tab-focus → Enter submits form)', async ({
		page,
	}) => {
		await page.goto('/login');

		await page.locator('#email').fill('invalid');
		await page.locator('#password').fill('secret');

		// 제출 버튼까지 Tab 이동 후 Enter
		await page.locator('#submit').focus();
		await expect(page.locator('#submit')).toBeFocused();

		// Enter 키 → submit 이벤트 발생 (fetch 는 인트라넷 mock 이 없어 실패하지만
		// 로딩 문구 "처리 중…" 이 표시되는지로 submit 트리거를 확인)
		await Promise.all([
			page.waitForFunction(() => {
				const btn = document.getElementById('submit') as HTMLButtonElement | null;
				return btn?.textContent?.includes('처리 중') ?? false;
			}, { timeout: 5_000 }),
			page.keyboard.press('Enter'),
		]);
	});

	test('Input focus shifts wrap border color (focus-within ring)', async ({ page }) => {
		await page.goto('/login');

		const email = page.locator('#email');
		const wrap = email.locator('xpath=ancestor::div[contains(@class,"input-wrap")][1]');

		// 포커스 전 border-color 캡처 — 활성 element 명시적 blur
		await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
		const before = await wrap.evaluate(
			(el) => window.getComputedStyle(el as HTMLElement).borderColor,
		);

		// 포커스 후 border-color 캡처
		await email.focus();
		await expect(email).toBeFocused();
		const after = await wrap.evaluate(
			(el) => window.getComputedStyle(el as HTMLElement).borderColor,
		);

		// focus-within 으로 border-color 가 변경되어야 함
		expect(after).not.toBe(before);
	});
});
