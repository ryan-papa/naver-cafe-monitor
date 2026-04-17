import { describe, expect, it, vi } from 'vitest';

// document + crypto mock setup
Object.defineProperty(globalThis, 'document', {
	value: { cookie: '' },
	writable: true,
});

import { readCookie } from './auth-client';

describe('readCookie', () => {
	it('returns value for exact match', () => {
		(document as { cookie: string }).cookie = 'csrf_token=abc123; other=xyz';
		expect(readCookie('csrf_token')).toBe('abc123');
	});
	it('returns null when not present', () => {
		(document as { cookie: string }).cookie = 'other=xyz';
		expect(readCookie('csrf_token')).toBeNull();
	});
	it('decodes url-encoded values', () => {
		(document as { cookie: string }).cookie = 'csrf_token=a%20b';
		expect(readCookie('csrf_token')).toBe('a b');
	});
});
