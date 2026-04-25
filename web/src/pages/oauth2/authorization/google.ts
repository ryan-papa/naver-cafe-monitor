import type { APIRoute } from "astro";
import { proxyApiRequest } from "../../../lib/server-api-proxy";

export const GET: APIRoute = (context) => {
	return proxyApiRequest(context, "/oauth2/authorization/google");
};
