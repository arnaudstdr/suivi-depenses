import {
  getCacheStorage,
  getPrivateJson,
  putPrivateJson,
} from "./privateCache";
import type { ApiErrorBody } from "./types";

export const DEFAULT_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export class NetworkError extends Error {
  constructor(message = "Réseau indisponible") {
    super(message);
    this.name = "NetworkError";
  }
}

export type ApiResult<T> = {
  data: T;
  fromCache: boolean;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  cacheUserId?: string;
  cacheTtlMs?: number;
  signal?: AbortSignal;
};

/**
 * Stratégie réseau d'abord, cache privé en secours.
 * Le cache n'est jamais servi à la place d'une réponse fraîche disponible.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResult<T>> {
  const method = options.method ?? "GET";
  const storage = getCacheStorage();
  const cacheUserId = options.cacheUserId;
  const canCache =
    method === "GET" && storage !== null && cacheUserId !== undefined;
  const ttlMs = options.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS;

  const headers = new Headers();
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD"].includes(method)) {
    headers.set("X-CSRF-Token", await csrfToken());
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (error) {
    if (canCache && storage !== null && cacheUserId !== undefined) {
      try {
        const cached = await getPrivateJson<T>(storage, cacheUserId, path);
        if (cached !== null) {
          return { data: cached, fromCache: true };
        }
      } catch {
        // Cache indisponible : on remonte l'erreur réseau d'origine.
      }
    }
    throw new NetworkError(error instanceof Error ? error.message : undefined);
  }

  if (response.status === 401) {
    notifyUnauthorized();
    throw new ApiError("Session expirée.", "unauthorized", 401);
  }

  if (!response.ok) {
    const body = await readError(response);
    throw new ApiError(
      body?.message ?? `Erreur HTTP ${response.status}.`,
      body?.code ?? "http_error",
      response.status,
    );
  }

  const data =
    response.status === 204 ? (undefined as T) : ((await response.json()) as T);

  if (canCache && storage !== null && cacheUserId !== undefined) {
    try {
      await putPrivateJson(storage, cacheUserId, path, data, { ttlMs });
    } catch {
      // L'échec du cache ne doit pas faire échouer une lecture réussie.
    }
  }

  return { data, fromCache: false };
}

export async function api<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  return (await apiRequest<T>(path, options)).data;
}

async function csrfToken(): Promise<string> {
  const fromCookie = readCookie("suivi_csrf");
  if (fromCookie) {
    return fromCookie;
  }
  const response = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new ApiError("Impossible d'obtenir le jeton CSRF.", "csrf_failed", 403);
  }
  const body = (await response.json()) as { csrf_token: string };
  return body.csrf_token;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length));
    }
  }
  return null;
}

async function readError(response: Response): Promise<ApiErrorBody | null> {
  try {
    return (await response.json()) as ApiErrorBody;
  } catch {
    return null;
  }
}

function notifyUnauthorized(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("suivi:unauthorized"));
  }
}
