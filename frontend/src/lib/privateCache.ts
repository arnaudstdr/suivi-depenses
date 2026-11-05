const CACHE_PREFIX = "suivi-private-v1";
const PRIVATE_PATH_PREFIX = "/__private_cache__";
const CACHED_AT_HEADER = "x-cached-at";
const TTL_HEADER = "x-cache-ttl-ms";

export interface CacheLike {
  put(request: RequestInfo | URL, response: Response): Promise<void>;
  match(request: RequestInfo | URL): Promise<Response | undefined>;
  delete(request: RequestInfo | URL): Promise<boolean>;
}

export interface CacheStorageLike {
  open(name: string): Promise<CacheLike>;
  delete(name: string): Promise<boolean>;
  keys(): Promise<string[]>;
}

export type Clock = () => number;

export function cacheNameForUser(userId: string): string {
  return `${CACHE_PREFIX}:${userId}`;
}

export function getCacheStorage(): CacheStorageLike | null {
  if (typeof caches === "undefined") {
    return null;
  }
  return caches as unknown as CacheStorageLike;
}

export async function putPrivateJson(
  storage: CacheStorageLike,
  userId: string,
  path: string,
  data: unknown,
  options: { ttlMs: number; now?: Clock },
): Promise<void> {
  const cache = await storage.open(cacheNameForUser(userId));
  const now = options.now ? options.now() : Date.now();
  const response = new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      "content-type": "application/json",
      [CACHED_AT_HEADER]: String(now),
      [TTL_HEADER]: String(options.ttlMs),
    },
  });
  await cache.put(privateRequest(path), response);
}

export async function getPrivateJson<T>(
  storage: CacheStorageLike,
  userId: string,
  path: string,
  options: { now?: Clock } = {},
): Promise<T | null> {
  const cache = await storage.open(cacheNameForUser(userId));
  const response = await cache.match(privateRequest(path));
  if (response === undefined) {
    return null;
  }
  const cachedAt = Number(response.headers.get(CACHED_AT_HEADER) ?? "0");
  const ttlMs = Number(response.headers.get(TTL_HEADER) ?? "0");
  const now = options.now ? options.now() : Date.now();
  if (cachedAt <= 0 || ttlMs <= 0 || now - cachedAt > ttlMs) {
    await cache.delete(privateRequest(path));
    return null;
  }
  return (await response.json()) as T;
}

export async function purgeUserCache(
  storage: CacheStorageLike,
  userId: string,
): Promise<void> {
  try {
    await storage.delete(cacheNameForUser(userId));
  } catch {
    // La purge est best-effort : ne jamais bloquer la déconnexion.
  }
}

export async function purgeAllPrivateCaches(
  storage: CacheStorageLike | null = getCacheStorage(),
): Promise<void> {
  if (storage === null) {
    return;
  }
  try {
    const names = await storage.keys();
    await Promise.all(
      names
        .filter((name) => name.startsWith(`${CACHE_PREFIX}:`))
        .map((name) => storage.delete(name)),
    );
  } catch {
    // La purge est best-effort : ne jamais bloquer la déconnexion.
  }
}

function privateRequest(path: string): Request {
  const origin =
    typeof location !== "undefined" ? location.origin : "https://suivi.local";
  return new Request(
    new URL(`${PRIVATE_PATH_PREFIX}${path}`, origin).toString(),
  );
}
