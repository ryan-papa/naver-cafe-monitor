import { defineMiddleware } from 'astro:middleware';
import { isPublic } from './lib/public-paths';

export const onRequest = defineMiddleware(async (context, next) => {
	const { pathname } = context.url;
	if (isPublic(pathname)) return next();

	const accessToken = context.cookies.get('access_token')?.value;
	if (!accessToken) {
		const target = new URL('/login', context.url);
		target.searchParams.set('next', pathname);
		return context.redirect(target.pathname + target.search, 302);
	}

	return next();
});
