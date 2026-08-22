/**
 * Browser controller for progressive game-image upscaling — SBGC-184.
 *
 * Orchestrates: eligibility → cache lookup → (cache miss) worker/WebSR → cache
 * → reveal. Every failure path leaves the original image untouched and does not
 * surface any user-facing error.
 */

import {
  buildCacheKey,
  decideEnhancement,
  isEligibleForUpscale,
  MODEL_VERSION,
  NETWORK_NAME,
  revealMode,
  UPSCALE_FACTOR,
} from "./game-image-upscale";
import {
  getCachedImage,
  putCachedImage,
  type CachedGameImage,
} from "./game-image-upscale-store";
// The WebSR UMD bundle must not be re-bundled as ESM (its class hierarchy
// breaks), so it is imported as a raw asset URL and loaded at runtime in a
// classic worker via `importScripts`.
import websrUrl from "@websr/websr/dist/websr.js?url";
import weights3d from "@websr/websr/weights/anime4k/cnn-2x-s-3d.json";

export interface MountOptions {
  root: HTMLElement;
  gameSlug: string;
  sourceUrl: string;
}

export function mountGameImageEnhancer(options: MountOptions): void {
  const { root, gameSlug, sourceUrl } = options;

  const original = root.querySelector<HTMLImageElement>(
    "[data-game-image-original]",
  );
  const overlay = root.querySelector<HTMLImageElement>(
    "[data-game-image-enhanced]",
  );
  if (!original || !overlay) return;

  const originalImage: HTMLImageElement = original;
  const overlayImage: HTMLImageElement = overlay;

  // Give the original at least one paint opportunity before any heavy work.
  const afterPaint = (fn: () => void): void => {
    requestAnimationFrame(() => requestAnimationFrame(fn));
  };

  const start = (): void => {
    const width = originalImage.naturalWidth;
    const height = originalImage.naturalHeight;
    const eligible = isEligibleForUpscale(width, height);
    console.info("[game-image]", "dimensions", { width, height, eligible });
    if (!eligible) return;
    void enhance(width, height);
  };

  if (originalImage.complete && originalImage.naturalWidth > 0) {
    afterPaint(start);
  } else {
    originalImage.addEventListener("load", () => afterPaint(start), {
      once: true,
    });
  }

  async function enhance(width: number, height: number): Promise<void> {
    const key = buildCacheKey({
      gameSlug,
      sourceUrl,
      modelVersion: MODEL_VERSION,
    });

    // Cache-before-inference: a valid cached result must bypass WebSR.
    const cached = await getCachedImage(key);
    const decision = decideEnhancement(true, cached !== null);
    console.info("[game-image]", "decision", decision);
    if (decision === "cache-hit" && cached) {
      reveal(cached.blob);
      return;
    }
    if (decision !== "cache-miss") return;

    await runInference(key, width, height);
  }

  async function runInference(
    key: string,
    width: number,
    height: number,
  ): Promise<void> {
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(originalImage);
    } catch (error) {
      console.info("[game-image]", "pixel-read blocked", error);
      return;
    }

    const worker = new Worker(
      new URL("./game-image-upscale.worker.ts", import.meta.url),
    );

    const blob = await new Promise<Blob | null>((resolve) => {
      worker.onmessage = (event: MessageEvent) => {
        const data = event.data as { type?: string; blob?: Blob } | null;
        console.info("[game-image]", "worker result", data?.type ?? "(none)");
        resolve(data?.type === "success" && data.blob ? data.blob : null);
      };
      worker.onerror = (error) => {
        console.info("[game-image]", "worker error", error.message);
        resolve(null);
      };
      worker.postMessage(
        {
          type: "upscale",
          bitmap,
          outputWidth: width * UPSCALE_FACTOR,
          outputHeight: height * UPSCALE_FACTOR,
          websrUrl,
          weights: weights3d,
          networkName: NETWORK_NAME,
        },
        [bitmap],
      );
    });

    worker.terminate();

    if (!blob) return;

    const now = Date.now();
    const record: CachedGameImage = {
      key,
      gameSlug,
      sourceUrl,
      modelVersion: MODEL_VERSION,
      blob,
      createdAt: now,
      lastAccessedAt: now,
    };
    await putCachedImage(record);
    reveal(blob);
  }

  function reveal(blob: Blob): void {
    const url = URL.createObjectURL(blob);
    overlayImage.hidden = false;
    const cleanup = () => URL.revokeObjectURL(url);
    overlayImage.addEventListener(
      "load",
      () => {
        overlayImage.dataset.reveal = revealMode(
          window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        );
        cleanup();
      },
      { once: true },
    );
    overlayImage.addEventListener("error", cleanup, { once: true });
    overlayImage.src = url;
  }
}
