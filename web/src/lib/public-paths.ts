export const PUBLIC_PATHS = new Set<string>([
	'/login',
	'/signup',
	'/error/401',
	'/error/403',
	'/error/404',
	'/error/500',
	'/error/offline',
]);

export const PUBLIC_PREFIXES = ['/_astro/', '/favicon.'];

export function isPublic(pathname: string): boolean {
	if (PUBLIC_PATHS.has(pathname)) return true;
	return PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
}
