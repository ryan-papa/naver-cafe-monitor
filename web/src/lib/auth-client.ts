/** 브라우저 auth helpers.
 *
 * - importPublicKey: /api/auth/public-key 의 PEM 을 Web Crypto 공개키로 변환
 * - encryptField: RSA-OAEP(SHA-256) 로 필드 암호화 → base64
 * - csrfFetch: state-changing 요청에 X-CSRF-Token 자동 주입, 401 시 refresh 후 1회 재시도
 * - readCookie: document.cookie 에서 csrf_token 읽기
 */

function pemToBytes(pem: string): Uint8Array {
	const b64 = pem.replace(/-----[^-]+-----/g, '').replace(/\s/g, '');
	const bin = atob(b64);
	const out = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
	return out;
}

export async function importPublicKey(pem: string): Promise<CryptoKey> {
	const bytes = pemToBytes(pem);
	return crypto.subtle.importKey(
		'spki',
		bytes,
		{ name: 'RSA-OAEP', hash: 'SHA-256' },
		false,
		['encrypt']
	);
}

export async function encryptField(pub: CryptoKey, value: string): Promise<string> {
	const ct = await crypto.subtle.encrypt(
		{ name: 'RSA-OAEP' },
		pub,
		new TextEncoder().encode(value)
	);
	const bytes = new Uint8Array(ct);
	let s = '';
	for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
	return btoa(s);
}

export async function fetchPublicKey(): Promise<CryptoKey> {
	const r = await fetch('/api/auth/public-key', { credentials: 'include' });
	if (!r.ok) throw new Error('failed to load public key');
	const { public_key_pem } = await r.json();
	return importPublicKey(public_key_pem);
}

export function readCookie(name: string): string | null {
	const target = name + '=';
	for (const raw of document.cookie.split(';')) {
		const c = raw.trim();
		if (c.startsWith(target)) return decodeURIComponent(c.slice(target.length));
	}
	return null;
}

interface CsrfFetchOptions extends RequestInit {
	retryOn401?: boolean;
}

export async function csrfFetch(url: string, opts: CsrfFetchOptions = {}): Promise<Response> {
	const method = (opts.method || 'GET').toUpperCase();
	const headers = new Headers(opts.headers);
	if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
		const csrf = readCookie('csrf_token');
		if (csrf) headers.set('X-CSRF-Token', csrf);
	}
	if (opts.body && !headers.has('content-type')) {
		headers.set('content-type', 'application/json');
	}

	const res = await fetch(url, { ...opts, headers, credentials: 'include' });
	if (res.status !== 401 || opts.retryOn401 === false) return res;

	// 1회 refresh 시도
	const rf = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' });
	if (!rf.ok) {
		window.location.assign(
			'/login?next=' + encodeURIComponent(window.location.pathname + window.location.search)
		);
		return res;
	}
	// 재시도 (retryOn401=false 로)
	return csrfFetch(url, { ...opts, retryOn401: false });
}
