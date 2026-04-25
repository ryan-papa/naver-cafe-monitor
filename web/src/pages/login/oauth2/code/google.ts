import type { APIRoute } from "astro";
import { proxyApiRequest } from "../../../../lib/server-api-proxy";

export const GET: APIRoute = (context) => {
	return proxyApiRequest(context, "/login/oauth2/code/google");
};
