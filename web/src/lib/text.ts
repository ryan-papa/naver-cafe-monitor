/**
 * collapseBlankLines: 본문 텍스트의 과도한 빈 줄 정리.
 * - 연속 빈 줄 1개(= `\n\n`) → 제거 (문단 연결)
 * - 연속 빈 줄 2개 이상(= `\n\n\n+`) → 1개로 축소
 * 공백·탭만 있는 줄도 빈 줄로 취급.
 */
export function collapseBlankLines(text: string): string {
	if (!text) return text;
	const lines = text.replace(/\r\n?/g, '\n').split('\n');
	const out: string[] = [];
	let blankRun = 0;
	let seenContent = false;
	for (const raw of lines) {
		const isBlank = raw.trim() === '';
		if (isBlank) {
			blankRun++;
			continue;
		}
		if (seenContent && blankRun >= 2) {
			out.push('');
		}
		out.push(raw);
		seenContent = true;
		blankRun = 0;
	}
	return out.join('\n');
}
