import { defineMiddleware } from 'astro:middleware';
import { isPublic } from './lib/public-paths';

const API_BASE = process.env.INTERNAL_API_BASE || 'http://127.0.0.1:8000';
const SETUP_PATH = '/admin/settings/2fa';

const LEGACY_REDIRECTS: Record<string, string> = {
	'/': '/admin',
	'/settings/2fa': '/admin/settings/2fa',
};

async function fetchMe(accessToken: string): Promise<{ totp_setup_required?: boolean } | null> {
	try {
		const r = await fetch(`${API_BASE}/api/auth/me`, {
			headers: { Cookie: `access_token=${accessToken}` },
		});
		if (!r.ok) return null;
		return (await r.json()) as { totp_setup_required?: boolean };
	} catch {
		return null;
	}
}

export const onRequest = defineMiddleware(async (context, next) => {
	const { pathname } = context.url;

	const legacyTarget = LEGACY_REDIRECTS[pathname];
	if (legacyTarget && legacyTarget !== pathname) {
		return context.redirect(legacyTarget, 302);
	}

	if (isPublic(pathname)) return next();

	const accessToken = context.cookies.get('access_token')?.value;
	if (!accessToken) {
		const target = new URL('/login', context.url);
		target.searchParams.set('next', pathname);
		return context.redirect(target.pathname + target.search, 302);
	}

	const me = await fetchMe(accessToken);
	if (me?.totp_setup_required && pathname !== SETUP_PATH) {
		return context.redirect(SETUP_PATH, 302);
	}

	return next();
});
