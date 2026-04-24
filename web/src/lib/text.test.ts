import { describe, expect, it } from 'vitest';
import { collapseBlankLines } from './text';

describe('collapseBlankLines', () => {
	it('removes single blank line between paragraphs', () => {
		expect(collapseBlankLines('A\n\nB')).toBe('A\nB');
	});

	it('keeps exactly one blank line when two or more blanks appear', () => {
		expect(collapseBlankLines('A\n\n\nB')).toBe('A\n\nB');
		expect(collapseBlankLines('A\n\n\n\n\nB')).toBe('A\n\nB');
	});

	it('treats a single whitespace-only line as one blank → removed', () => {
		expect(collapseBlankLines('A\n   \nB')).toBe('A\nB');
	});

	it('treats two whitespace-only lines as two blanks → kept as one', () => {
		expect(collapseBlankLines('A\n   \n\t\nB')).toBe('A\n\nB');
	});

	it('preserves leading content and trims leading blanks', () => {
		expect(collapseBlankLines('\n\nA\n\n\nB')).toBe('A\n\nB');
	});

	it('drops trailing blanks', () => {
		expect(collapseBlankLines('A\n\n\n')).toBe('A');
	});

	it('normalizes CRLF line endings', () => {
		expect(collapseBlankLines('A\r\n\r\nB\r\n\r\n\r\nC')).toBe('A\nB\n\nC');
	});

	it('returns empty input unchanged', () => {
		expect(collapseBlankLines('')).toBe('');
	});

	it('handles text without blank lines', () => {
		expect(collapseBlankLines('A\nB\nC')).toBe('A\nB\nC');
	});
});
