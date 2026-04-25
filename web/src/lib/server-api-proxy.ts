import type { APIContext } from "astro";

const API_BASE =
	import.meta.env.INTERNAL_API_BASE || process.env.INTERNAL_API_BASE || "http://127.0.0.1:8000";

const HOP_BY_HOP = new Set([
	"connection",
	"content-encoding",
	"content-length",
	"keep-alive",
	"transfer-encoding",
	"upgrade",
]);

export async function proxyApiRequest(context: APIContext, targetPath: string): Promise<Response> {
	const target = new URL(targetPath + context.url.search, API_BASE);
	const headers = new Headers();
	const cookie = context.request.headers.get("cookie");
	if (cookie) headers.set("cookie", cookie);
	const userAgent = context.request.headers.get("user-agent");
	if (userAgent) headers.set("user-agent", userAgent);

	const upstream = await fetch(target, {
		method: context.request.method,
		headers,
		redirect: "manual",
	});

	const responseHeaders = new Headers();
	upstream.headers.forEach((value, key) => {
		const lower = key.toLowerCase();
		if (!HOP_BY_HOP.has(lower) && lower !== "set-cookie") responseHeaders.append(key, value);
	});
	const getSetCookie = (upstream.headers as Headers & { getSetCookie?: () => string[] })
		.getSetCookie;
	for (const cookieValue of getSetCookie?.call(upstream.headers) ?? []) {
		responseHeaders.append("set-cookie", cookieValue);
	}

	return new Response(upstream.body, {
		status: upstream.status,
		statusText: upstream.statusText,
		headers: responseHeaders,
	});
}
