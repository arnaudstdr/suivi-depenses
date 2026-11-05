import { describe, expect, it } from "vitest";

import {
  type CacheLike,
  type CacheStorageLike,
  cacheNameForUser,
  getPrivateJson,
  purgeAllPrivateCaches,
  purgeUserCache,
  putPrivateJson,
} from "./privateCache";

class FakeCache implements CacheLike {
  private readonly entries = new Map<string, Response>();

  async put(request: RequestInfo | URL, response: Response): Promise<void> {
    this.entries.set(requestKey(request), response.clone());
  }

  async match(request: RequestInfo | URL): Promise<Response | undefined> {
    return this.entries.get(requestKey(request))?.clone();
  }

  async delete(request: RequestInfo | URL): Promise<boolean> {
    return this.entries.delete(requestKey(request));
  }
}

class FakeCacheStorage implements CacheStorageLike {
  private readonly caches = new Map<string, FakeCache>();

  async open(name: string): Promise<CacheLike> {
    let cache = this.caches.get(name);
    if (cache === undefined) {
      cache = new FakeCache();
      this.caches.set(name, cache);
    }
    return cache;
  }

  async delete(name: string): Promise<boolean> {
    return this.caches.delete(name);
  }

  async keys(): Promise<string[]> {
    return [...this.caches.keys()];
  }
}

function requestKey(request: RequestInfo | URL): string {
  return typeof request === "string" ? request : request.toString();
}

describe("privateCache", () => {
  it("isole les données par utilisateur", async () => {
    const storage = new FakeCacheStorage();

    await putPrivateJson(storage, "user-a", "/api/v1/dashboard", { value: 1 }, {
      ttlMs: 60_000,
    });

    expect(
      await getPrivateJson(storage, "user-a", "/api/v1/dashboard"),
    ).toEqual({ value: 1 });
    expect(
      await getPrivateJson(storage, "user-b", "/api/v1/dashboard"),
    ).toBeNull();
    expect(cacheNameForUser("user-a")).not.toBe(cacheNameForUser("user-b"));
  });

  it("supprime le cache d'un seul utilisateur", async () => {
    const storage = new FakeCacheStorage();

    await putPrivateJson(storage, "user-a", "/api/v1/me", { user: "a" }, {
      ttlMs: 60_000,
    });
    await putPrivateJson(storage, "user-b", "/api/v1/me", { user: "b" }, {
      ttlMs: 60_000,
    });

    await purgeUserCache(storage, "user-a");

    expect(await getPrivateJson(storage, "user-a", "/api/v1/me")).toBeNull();
    expect(await getPrivateJson(storage, "user-b", "/api/v1/me")).toEqual({
      user: "b",
    });
  });

  it("purge tous les caches privés sans toucher aux autres", async () => {
    const storage = new FakeCacheStorage();

    await putPrivateJson(storage, "user-a", "/api/v1/me", { user: "a" }, {
      ttlMs: 60_000,
    });
    await putPrivateJson(storage, "user-b", "/api/v1/me", { user: "b" }, {
      ttlMs: 60_000,
    });
    await storage.open("public-assets");

    await purgeAllPrivateCaches(storage);

    expect((await storage.keys()).sort()).toEqual(["public-assets"]);
  });

  it("ignore une entrée expirée", async () => {
    const storage = new FakeCacheStorage();
    let now = 1_000;

    await putPrivateJson(storage, "user-a", "/api/v1/me", { user: "a" }, {
      ttlMs: 100,
      now: () => now,
    });

    now = 1_050;
    expect(await getPrivateJson(storage, "user-a", "/api/v1/me", {
      now: () => now,
    })).toEqual({ user: "a" });

    now = 1_101;
    expect(await getPrivateJson(storage, "user-a", "/api/v1/me", {
      now: () => now,
    })).toBeNull();
  });
});
