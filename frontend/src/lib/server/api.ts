import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Me } from "@/lib/types";

const API_ORIGIN = process.env.LODGEOS_API_ORIGIN ?? "http://127.0.0.1:8000";

export class ServerApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * GET from the API during server rendering, forwarding the visitor's cookies.
 * The API remains the authority on permissions; this only decides what to render.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const res = await fetch(`${API_ORIGIN}${path}`, {
    headers: { cookie: cookieHeader, accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ServerApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** The signed-in user, or a redirect to the sign-in page. */
export async function requireMe(): Promise<Me> {
  try {
    return await apiGet<Me>("/api/v1/auth/me");
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) redirect("/sign-in");
    throw err;
  }
}

/** The signed-in user with an active organisation, or the relevant redirect. */
export async function requireOrganisation(): Promise<Me & { active_organisation: NonNullable<Me["active_organisation"]> }> {
  const me = await requireMe();
  if (!me.active_organisation) redirect("/select-organisation");
  return me as Me & { active_organisation: NonNullable<Me["active_organisation"]> };
}
