import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "./api";
import {
  type CacheLike,
  type CacheStorageLike,
  getPrivateJson,
  putPrivateJson,
} from "./privateCache";

class FakeCache implements CacheLike {
  private readonly entries = new Map<string, Response>();

  async put(request: RequestInfo | URL, response: Response): Promise<void> {
    this.entries.set(String(request), response.clone());
  }

  async match(request: RequestInfo | URL): Promise<Response | undefined> {
    return this.entries.get(String(request))?.clone();
  }

  async delete(request: RequestInfo | URL): Promise<boolean> {
    return this.entries.delete(String(request));
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

describe("apiRequest", () => {
  let storage: FakeCacheStorage;

  beforeEach(() => {
    storage = new FakeCacheStorage();
    vi.stubGlobal("caches", storage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("privilégie le réseau et met à jour le cache", async () => {
    await putPrivateJson(storage, "user-a", "/api/v1/dashboard", {
      value: "cache",
    }, { ttlMs: 60_000 });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ value: "frais" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const result = await apiRequest<{ value: string }>(
      "/api/v1/dashboard",
      { cacheUserId: "user-a" },
    );

    expect(result).toEqual({ data: { value: "frais" }, fromCache: false });
    expect(
      await getPrivateJson(storage, "user-a", "/api/v1/dashboard"),
    ).toEqual({ value: "frais" });
  });

  it("retombe sur le cache privé lorsque le réseau échoue", async () => {
    await putPrivateJson(storage, "user-a", "/api/v1/dashboard", {
      value: "cache",
    }, { ttlMs: 60_000 });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const result = await apiRequest<{ value: string }>(
      "/api/v1/dashboard",
      { cacheUserId: "user-a" },
    );

    expect(result).toEqual({ data: { value: "cache" }, fromCache: true });
  });

  it("ne sert jamais le cache d'un autre utilisateur", async () => {
    await putPrivateJson(storage, "user-a", "/api/v1/dashboard", {
      value: "cache-a",
    }, { ttlMs: 60_000 });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(
      apiRequest("/api/v1/dashboard", { cacheUserId: "user-b" }),
    ).rejects.toThrow("offline");
  });
});
