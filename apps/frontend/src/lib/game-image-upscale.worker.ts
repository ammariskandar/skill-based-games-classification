/**
 * Web Worker for WebSR 2x upscaling — SBGC-184.
 *
 * Browser-only and WebGPU-only. All failures are reported back to the
 * controller, which keeps the original image. The WebSR library's published
 * types annotate the output canvas as `HTMLCanvasElement`, but its runtime
 * supports `OffscreenCanvas` (documented upstream), which is what a worker can
 * create.
 */

import WebSR from "@websr/websr";
import weights3d from "@websr/websr/weights/anime4k/cnn-2x-s-3d.json";

import { NETWORK_NAME, upscaleDimensions } from "./game-image-upscale";

export interface UpscaleRequest {
  type: "upscale";
  bitmap: ImageBitmap;
  width: number;
  height: number;
}

export type UpscaleResponse =
  | { type: "success"; blob: Blob; width: number; height: number }
  | { type: "unsupported" }
  | { type: "failed" };

/** Minimal worker-scope surface (the DOM lib types `self` as `Window`). */
interface WorkerScope {
  onmessage: ((event: MessageEvent<UpscaleRequest>) => void) | null;
  postMessage(message: UpscaleResponse): void;
}

const scope = self as unknown as WorkerScope;

scope.onmessage = async (event) => {
  const request = event.data;
  if (request?.type !== "upscale") return;

  try {
    const gpu = await WebSR.initWebGPU();
    console.info("[game-image-worker]", "initWebGPU", Boolean(gpu));
    if (!gpu) {
      scope.postMessage({ type: "unsupported" });
      return;
    }

    const { width, height } = upscaleDimensions(request.width, request.height);
    const canvas = new OffscreenCanvas(width, height);

    const websr = new WebSR({
      // Upstream types omit OffscreenCanvas, but the runtime accepts it.
      canvas: canvas as unknown as HTMLCanvasElement,
      weights: weights3d,
      network_name: NETWORK_NAME,
      gpu,
    });

    await websr.render(request.bitmap);

    const blob = await canvas.convertToBlob({
      type: "image/webp",
      quality: 0.9,
    });

    await websr.destroy();

    console.info("[game-image-worker]", "success", {
      width,
      height,
      bytes: blob.size,
    });

    scope.postMessage({ type: "success", blob, width, height });
  } catch (error) {
    console.info("[game-image-worker]", "failed", error);
    scope.postMessage({ type: "failed" });
  }
};
