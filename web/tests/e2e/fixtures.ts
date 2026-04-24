import { expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * axe-core 접근성 검증 헬퍼.
 *
 * critical/serious 수준 위반 0건만 허용.
 * moderate/minor 는 QA 회고에서 별도 트래킹.
 */
export async function runA11y(page: Page): Promise<void> {
	const results = await new AxeBuilder({ page }).analyze();
	const violations = results.violations.filter((v) =>
		['critical', 'serious'].includes(v.impact ?? ''),
	);
	expect(
		violations,
		`axe violations (critical/serious):\n${JSON.stringify(violations, null, 2)}`,
	).toEqual([]);
}
