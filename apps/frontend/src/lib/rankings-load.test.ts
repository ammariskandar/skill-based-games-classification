import { afterEach, describe, expect, it, vi } from "vitest";

import {
  activeRankingsAbortController,
  buildRankingsUrl,
  fetchRankings,
  type RankingsLoadTarget,
} from "./rankings-load";

const TARGET: RankingsLoadTarget = {
  profile: "unified",
  dimension: "micro",
  direction: "desc",
  page: 1,
  pageSize: 5,
};

const BODY = {
  count: 1,
  page: 1,
  page_size: 5,
  total_pages: 1,
  results: [],
};

function jsonResponse(): Response {
  return new Response(JSON.stringify(BODY), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  activeRankingsAbortController()?.abort();
});

describe("fetchRankings", () => {
  it("fetches the canonical URL and returns parsed JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchRankings(TARGET);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(buildRankingsUrl(TARGET));
    expect(result).toEqual(BODY);
  });

  it("aborts the previous in-flight request when a new one starts", () => {
    const signals: AbortSignal[] = [];
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      signals.push(init?.signal as AbortSignal);
      return new Promise<Response>(() => {});
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = fetchRankings(TARGET);
    void first.catch(() => {});
    const second = fetchRankings(TARGET);
    void second.catch(() => {});

    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it("clears the active controller once a request completes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse()));

    await fetchRankings(TARGET);
    expect(activeRankingsAbortController()).toBeNull();
  });

  it("surfaces an AbortError as a rejection, not a crash", async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        (init?.signal as AbortSignal).addEventListener(
          "abort",
          () =>
            reject(
              new DOMException("The user aborted a request.", "AbortError"),
            ),
          { once: true },
        );
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const pending = fetchRankings(TARGET);
    activeRankingsAbortController()?.abort();

    await expect(pending).rejects.toBeInstanceOf(DOMException);
  });

  it("rejects on a non-2xx HTTP response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("oops", { status: 503 })),
    );

    await expect(fetchRankings(TARGET)).rejects.toThrow("HTTP error: 503");
  });
});
