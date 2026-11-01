import { afterEach, describe, expect, it, vi } from "vitest";

// Reloading models an empty browser session and resets the private token cache.
async function api() {
  vi.resetModules();
  return import("./api");
}
const ok = (data: object, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => vi.unstubAllGlobals());
describe("same-origin API session and CSRF", () => {
  it.each(["consume", "receipt", "purchase"])(
    "never retries %s when its response is lost",
    async (operation) => {
      const fetch = vi
        .fn()
        .mockResolvedValueOnce(
          ok({ authenticated: true, csrf_token: "fixture" }),
        )
        .mockRejectedValueOnce(new TypeError("Failed to fetch"));
      vi.stubGlobal("fetch", fetch);
      const client = await api();
      const call =
        operation === "consume"
          ? client.consumeCatalogProduct(
              7,
              "0.25",
              "3",
              true,
              "operation-fixture",
            )
          : operation === "receipt"
            ? client.commitReceipt("ticket-fixture")
            : client.addShoppingAmount(7, "2", 9, "operation-fixture");
      await expect(call).rejects.toThrow("Failed to fetch");
      expect(fetch).toHaveBeenCalledTimes(2);
      expect(fetch.mock.calls[1][1]).toMatchObject({
        method: "POST",
        credentials: "same-origin",
      });
    },
  );

  it("expires the UI session after an unauthorized write without replaying it", async () => {
    const expired = vi.fn();
    window.addEventListener("despensa:session-expired", expired);
    try {
      const fetch = vi
        .fn()
        .mockResolvedValueOnce(
          ok({ authenticated: true, csrf_token: "fixture" }),
        )
        .mockResolvedValueOnce(ok({}, 401));
      vi.stubGlobal("fetch", fetch);
      await expect((await api()).removeShopping(12)).rejects.toThrow();
      expect(expired).toHaveBeenCalledOnce();
      expect(fetch).toHaveBeenCalledTimes(2);
    } finally {
      window.removeEventListener("despensa:session-expired", expired);
    }
  });
  it("bootstraps anonymous login with the public auth status token", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        ok({ authenticated: false, ingress: false, csrf_token: "anonymous" }),
      )
      .mockResolvedValueOnce(
        ok({ authenticated: true, csrf_token: "logged-in" }),
      );
    vi.stubGlobal("fetch", fetch);
    await (await api()).loginStandalone("test-password");
    expect(fetch.mock.calls[0][0]).toBe("api/v1/auth/status");
    expect(fetch.mock.calls[1][1]).toMatchObject({
      credentials: "same-origin",
      headers: { "X-CSRF-Token": "anonymous" },
      body: JSON.stringify({ password: "test-password" }),
    });
  });
  it("invalidates CSRF after every failed write, including multipart uploads", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(ok({ authenticated: true, csrf_token: "old" }))
      .mockResolvedValueOnce(ok({ error: "expired" }, 403))
      .mockResolvedValueOnce(ok({ authenticated: true, csrf_token: "fresh" }))
      .mockResolvedValueOnce(ok({}));
    vi.stubGlobal("fetch", fetch);
    const client = await api();
    await expect(
      client.uploadCatalogPhoto(7, new File(["image"], "test.jpg")),
    ).rejects.toThrow("expired");
    await client.removeShopping(4);
    expect(fetch.mock.calls[2][0]).toBe("api/v1/auth/status");
    expect(fetch.mock.calls[3][1].headers["X-CSRF-Token"]).toBe("fresh");
    expect(fetch).toHaveBeenCalledTimes(4); // No mutation is retried automatically.
  });
  it("reports expired auth on reads and handles HTML gateway failures", async () => {
    const expired = vi.fn();
    window.addEventListener("despensa:session-expired", expired);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(ok({}, 401))
        .mockResolvedValueOnce(
          new Response("<html>Gateway</html>", { status: 502 }),
        ),
    );
    const client = await api();
    await expect(client.getInventory()).rejects.toThrow();
    expect(expired).toHaveBeenCalledOnce();
    await expect(client.getShopping()).rejects.toThrow("Comprueba la conexión");
    window.removeEventListener("despensa:session-expired", expired);
  });
});
