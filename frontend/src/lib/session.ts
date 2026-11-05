import { ApiError, NetworkError, apiRequest } from "./api";
import {
  getCacheStorage,
  purgeAllPrivateCaches,
  purgeUserCache,
} from "./privateCache";
import type { AuthContext } from "./types";

const LAST_USER_KEY = "suivi.lastUserId";
const LAST_SYNC_KEY = "suivi.lastSyncAt";

export type LoadedSession = {
  context: AuthContext;
  fromCache: boolean;
};

export async function loadSession(): Promise<LoadedSession | null> {
  const lastUserId = storageGet(LAST_USER_KEY);
  try {
    const result = await apiRequest<AuthContext>("/api/v1/auth/me", {
      cacheUserId: lastUserId ?? undefined,
    });
    if (lastUserId !== null && lastUserId !== result.data.user.id) {
      await purgeAllPrivateCaches(getCacheStorage());
    }
    storageSet(LAST_USER_KEY, result.data.user.id);
    if (!result.fromCache) {
      markSynced();
    }
    return { context: result.data, fromCache: result.fromCache };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      await clearLocalSession();
      return null;
    }
    throw error;
  }
}

export async function loginSession(
  email: string,
  password: string,
): Promise<AuthContext> {
  await purgeAllPrivateCaches(getCacheStorage());
  const context = (
    await apiRequest<AuthContext>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    })
  ).data;
  storageSet(LAST_USER_KEY, context.user.id);
  markSynced();
  return context;
}

export async function logoutSession(): Promise<void> {
  try {
    await apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
  } catch (error) {
    if (!(error instanceof NetworkError)) {
      // La purge locale reste obligatoire même si le serveur est indisponible.
      await clearLocalSession();
    }
  } finally {
    await clearLocalSession();
  }
}

export async function clearLocalSession(): Promise<void> {
  await purgeAllPrivateCaches(getCacheStorage());
  storageRemove(LAST_USER_KEY);
  storageRemove(LAST_SYNC_KEY);
}

export async function purgeCurrentUserCache(userId: string): Promise<void> {
  await purgeUserCacheStorage(userId);
}

export function markSynced(): void {
  storageSet(LAST_SYNC_KEY, new Date().toISOString());
}

export function getLastSyncedAt(): string | null {
  return storageGet(LAST_SYNC_KEY);
}

async function purgeUserCacheStorage(userId: string): Promise<void> {
  const storage = getCacheStorage();
  if (storage !== null) {
    await purgeUserCache(storage, userId);
  }
}

function storageGet(key: string): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key: string, value: string): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.setItem(key, value);
  } catch {
    // Le stockage peut être indisponible en navigation privée.
  }
}

function storageRemove(key: string): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.removeItem(key);
  } catch {
    // Le stockage peut être indisponible en navigation privée.
  }
}
