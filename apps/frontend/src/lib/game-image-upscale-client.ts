/**
 * Browser controller for progressive game-image upscaling — SBGC-184.
 *
 * Orchestrates: eligibility → cache lookup → (cache miss) worker/WebSR → cache
 * → reveal. Every failure path leaves the original image untouched and does not
 * surface any user-facing error.
 *
 * Role-aware: the Library Capsule uses a display-density rule (rendered CSS ×
 * DPR × 1.25 headroom); the header fallback and Manual primary image use the
 * width threshold rule. The cache key includes the asset role so a header and a
 * capsule for the same Game never collide.
 */

import {
  buildCacheKey,
  decideEnhancement,
  isEligibleForUpscale,
  isEligibleForUpscaleByDensity,
  MODEL_VERSION,
  NETWORK_NAME,
  revealMode,
  transitionMode,
  UPSCALE_FACTOR,
  type AssetRole,
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
  assetRole: AssetRole;
  sourceUrl: string;
}

export function mountGameImageEnhancer(options: MountOptions): void {
  const { root, gameSlug, assetRole, sourceUrl } = options;

  const original = root.querySelector<HTMLImageElement>(
    "[data-game-image-original]",
  );
  const overlay = root.querySelector<HTMLImageElement>(
    "[data-game-image-enhanced]",
  );
  if (!original || !overlay) return;

  const originalImage: HTMLImageElement = original;
  const overlayImage: HTMLImageElement = overlay;
  overlayImage.dataset.transition = transitionMode(assetRole);

  // Give the original at least one paint opportunity before any heavy work.
  const afterPaint = (fn: () => void): void => {
    requestAnimationFrame(() => requestAnimationFrame(fn));
  };

  const start = (): void => {
    const width = originalImage.naturalWidth;
    const height = originalImage.naturalHeight;
    const eligible = isEligible(assetRole, originalImage, width, height);
    console.info("[game-image]", "dimensions", {
      role: assetRole,
      width,
      height,
      eligible,
    });
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

  function isEligible(
    role: AssetRole,
    image: HTMLImageElement,
    width: number,
    height: number,
  ): boolean {
    if (role === "library-capsule") {
      const rect = image.getBoundingClientRect();
      return isEligibleForUpscaleByDensity(
        width,
        height,
        rect.width,
        rect.height,
        window.devicePixelRatio,
      );
    }
    return isEligibleForUpscale(width, height);
  }

  async function enhance(width: number, height: number): Promise<void> {
    const key = buildCacheKey({
      gameSlug,
      assetRole,
      sourceUrl,
      modelVersion: MODEL_VERSION,
    });

    // Cache-before-inference: a valid cached result must bypass WebSR.
    const cached = await getCachedImage(key);
    const decision = decideEnhancement(true, cached !== null);
    console.info("[game-image]", "decision", { role: assetRole, decision });
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
      console.info("[game-image]", "pixel-read blocked", {
        role: assetRole,
        error,
      });
      return;
    }

    const worker = new Worker(
      new URL("./game-image-upscale.worker.ts", import.meta.url),
    );

    const blob = await new Promise<Blob | null>((resolve) => {
      worker.onmessage = (event: MessageEvent) => {
        const data = event.data as { type?: string; blob?: Blob } | null;
        console.info("[game-image]", "worker result", {
          role: assetRole,
          type: data?.type ?? "(none)",
        });
        resolve(data?.type === "success" && data.blob ? data.blob : null);
      };
      worker.onerror = (error) => {
        console.info("[game-image]", "worker error", {
          role: assetRole,
          message: error.message,
        });
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
      assetRole,
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
        console.info("[game-image]", "revealed", {
          role: assetRole,
          mode: overlayImage.dataset.reveal,
          transition: overlayImage.dataset.transition,
          overlayWidth: overlayImage.naturalWidth,
          overlayHeight: overlayImage.naturalHeight,
          originalWidth: originalImage.naturalWidth,
          originalHeight: originalImage.naturalHeight,
        });
      },
      { once: true },
    );
    overlayImage.addEventListener("error", cleanup, { once: true });
    overlayImage.src = url;
  }
}
