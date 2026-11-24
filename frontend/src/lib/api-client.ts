/**
 * Browser-side API calls. Requests go to this origin's /api/* (forwarded to the API),
 * carry the session cookie automatically, and send the CSRF token on unsafe methods.
 */

const CSRF_COOKIE = "lodgeos_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

async function csrfToken(): Promise<string> {
  let token = readCookie(CSRF_COOKIE);
  if (!token) {
    await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
    token = readCookie(CSRF_COOKIE);
  }
  if (!token) throw new ApiError(0, "Could not start a secure session. Check that cookies are enabled.");
  return token;
}

type ValidationItem = { loc?: (string | number)[]; msg?: string };

async function toError(res: Response): Promise<ApiError> {
  let message = "Something went wrong. Please try again.";
  const fieldErrors: Record<string, string> = {};
  try {
    const body = (await res.json()) as { detail?: string | ValidationItem[] };
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      message = "Please check the highlighted fields.";
      for (const item of body.detail) {
        const field = item.loc?.[item.loc.length - 1];
        if (typeof field === "string" && item.msg) fieldErrors[field] = item.msg.replace(/^Value error, /, "");
      }
    }
  } catch {
    if (res.status >= 500) message = "The server is unavailable. Please try again shortly.";
  }
  return new ApiError(res.status, message, fieldErrors);
}

export async function api<T = void>(
  path: string,
  init: { method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"; body?: unknown } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { accept: "application/json" };
  if (method !== "GET") headers[CSRF_HEADER] = await csrfToken();
  if (init.body !== undefined) headers["content-type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "No connection. Check your internet connection and try again.");
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Upload an image file as the raw request body (ADR-0014). */
export async function uploadImage<T>(path: string, file: File): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { accept: "application/json", [CSRF_HEADER]: await csrfToken(), "content-type": file.type || "application/octet-stream" },
      credentials: "same-origin",
      body: file,
    });
  } catch {
    throw new ApiError(0, "The upload did not complete. Check your connection and try again.");
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}
