import { describe, expect, it } from 'vitest';
import { isPublic } from './public-paths';

describe('isPublic', () => {
	it.each(['/login', '/signup', '/error/401', '/error/404', '/error/500'])(
		'returns true for public path %s',
		(p) => expect(isPublic(p)).toBe(true)
	);

	it.each(['/', '/dashboard', '/settings/profile'])(
		'returns false for protected path %s',
		(p) => expect(isPublic(p)).toBe(false)
	);

	it('allows asset prefixes', () => {
		expect(isPublic('/_astro/index.js')).toBe(true);
		expect(isPublic('/favicon.ico')).toBe(true);
	});
});
