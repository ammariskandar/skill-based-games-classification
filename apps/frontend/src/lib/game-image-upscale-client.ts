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
  revealMode,
} from "./game-image-upscale";
import {
  getCachedImage,
  putCachedImage,
  type CachedGameImage,
} from "./game-image-upscale-store";

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
    if (!isEligibleForUpscale(width, height)) return;
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
    } catch {
      // Cross-origin pixel-read blocked (tainted canvas) — original stays.
      return;
    }

    const worker = new Worker(
      new URL("./game-image-upscale.worker.ts", import.meta.url),
      { type: "module" },
    );

    const blob = await new Promise<Blob | null>((resolve) => {
      worker.onmessage = (event: MessageEvent) => {
        const data = event.data as { type?: string; blob?: Blob } | null;
        resolve(data?.type === "success" && data.blob ? data.blob : null);
      };
      worker.onerror = () => resolve(null);
      worker.postMessage({ type: "upscale", bitmap, width, height }, [bitmap]);
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
