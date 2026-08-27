/**
 * Browser controller for progressive game-image upscaling — SBGC-184 / SBGC-202.
 *
 * Orchestrates: feature gate → eligibility → environmental gating → cache lookup
 * → (cache miss) worker/WebSR → cache → reveal.  Every failure path leaves the
 * original image untouched and does not surface any user-facing error.
 *
 * SBGC-202 hardens this path: automatic WebSR is disabled by default, gated on
 * viewport/visibility/data-saver, bounded by a 5s timeout, and teardown-safe.
 */

import {
  buildCacheKey,
  decideEnhancement,
  isEligibleForUpscale,
  isEligibleForUpscaleByDensity,
  isImageUpscalingEnabled,
  MODEL_VERSION,
  NETWORK_NAME,
  revealMode,
  shouldRunInference,
  transitionMode,
  UPSCALE_FACTOR,
  withTimeout,
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

const INFERENCE_TIMEOUT_MS = 5000;

export interface MountOptions {
  root: HTMLElement;
  gameSlug: string;
  assetRole: AssetRole;
  sourceUrl: string;
}

export interface EnhancerHandle {
  /** Detach observers/timers so a navigating page never commits stale work. */
  disconnect: () => void;
}

function isDataSaver(): boolean {
  const nav = navigator as Navigator & {
    connection?: { saveData?: boolean };
  };
  return nav.connection?.saveData === true;
}

export function mountGameImageEnhancer(options: MountOptions): EnhancerHandle {
  const { root, gameSlug, assetRole, sourceUrl } = options;

  const setStatus = (status: string): void => {
    root.dataset.upscaleStatus = status;
  };

  // Disabled by default: no worker, no observer, no model loading.
  if (!isImageUpscalingEnabled(import.meta.env.PUBLIC_ENABLE_IMAGE_UPSCALE)) {
    setStatus("disabled");
    return { disconnect: () => {} };
  }

  const original = root.querySelector<HTMLImageElement>(
    "[data-game-image-original]",
  );
  const overlay = root.querySelector<HTMLImageElement>(
    "[data-game-image-enhanced]",
  );
  if (!original || !overlay) {
    setStatus("disabled");
    return { disconnect: () => {} };
  }

  const originalImage: HTMLImageElement = original;
  const overlayImage: HTMLImageElement = overlay;
  overlayImage.dataset.transition = transitionMode(assetRole);

  let disposed = false;
  let observer: IntersectionObserver | null = null;
  setStatus("pending");

  const disconnect = (): void => {
    disposed = true;
    observer?.disconnect();
  };

  const afterPaint = (fn: () => void): void => {
    requestAnimationFrame(() => requestAnimationFrame(fn));
  };

  const scheduleIdle = (fn: () => void): void => {
    if (typeof window.requestIdleCallback === "function") {
      window.requestIdleCallback(fn, { timeout: 2000 });
    } else {
      window.setTimeout(fn, 0);
    }
  };

  const begin = (): void => {
    if (disposed || !root.isConnected) return;
    // The observer already confirmed intersection (or none is available), so
    // `isIntersecting` is `true`; visibility and data-saver are checked here.
    if (
      !shouldRunInference({
        isIntersecting: true,
        isVisible: document.visibilityState === "visible",
        saveData: isDataSaver(),
      })
    ) {
      return;
    }

    const width = originalImage.naturalWidth;
    const height = originalImage.naturalHeight;
    if (!isEligible(assetRole, originalImage, width, height)) {
      setStatus("unsupported");
      return;
    }

    scheduleIdle(() => void enhance(width, height));
  };

  const start = (): void => {
    if (typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              observer?.disconnect();
              begin();
              return;
            }
          }
        },
        { rootMargin: "50px" },
      );
      observer.observe(originalImage);
    } else {
      begin();
    }
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

    const cached = await getCachedImage(key);
    if (disposed || !root.isConnected) return;

    const decision = decideEnhancement(true, cached !== null);
    console.info("[game-image]", "decision", { role: assetRole, decision });
    if (decision === "cache-hit" && cached) {
      reveal(cached.blob);
      setStatus("enhanced");
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
      setStatus("unsupported");
      return;
    }

    if (disposed || !root.isConnected) return;

    const worker = new Worker(
      new URL("./game-image-upscale.worker.ts", import.meta.url),
    );

    const workerResult = new Promise<Blob | null>((resolve) => {
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

    let blob: Blob | null;
    try {
      blob = await withTimeout(workerResult, INFERENCE_TIMEOUT_MS, () =>
        worker.terminate(),
      );
    } catch {
      worker.terminate();
      setStatus("timeout");
      return;
    }
    worker.terminate();

    // The component may have been unmounted or navigated away mid-flight.
    if (disposed || !root.isConnected) return;
    if (!blob) {
      setStatus("unsupported");
      return;
    }

    const now = Date.now();
    const record: CachedGameImage = {
      key,
      gameSlug,
      assetRole,
      sourceUrl,
      modelVersion: MODEL_VERSION,
      blob,
      size: blob.size,
      createdAt: now,
      lastAccessedAt: now,
    };
    await putCachedImage(record);
    if (disposed || !root.isConnected) return;

    reveal(blob);
    setStatus("enhanced");
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

  return { disconnect };
}
