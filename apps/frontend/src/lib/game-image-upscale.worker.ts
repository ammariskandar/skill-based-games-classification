/**
 * Classic Web Worker for WebSR 2x upscaling — SBGC-184.
 *
 * WebSR ships a webpack UMD bundle whose internal class hierarchy breaks when it
 * is re-bundled as an ESM module (`Class extends value undefined`). This worker
 * therefore loads the UMD bundle at runtime via `importScripts` and reaches it
 * through the `self.WebSR` global, exactly as WebSR's own worker example does.
 */

import { NETWORK_NAME, upscaleDimensions } from "./game-image-upscale";

export interface UpscaleRequest {
  type: "upscale";
  bitmap: ImageBitmap;
  width: number;
  height: number;
  websrUrl: string;
  weights: unknown;
}

export type UpscaleResponse =
  | { type: "success"; blob: Blob; width: number; height: number }
  | { type: "unsupported" }
  | { type: "failed" };

interface WebSrInstance {
  render(source: ImageBitmap): Promise<void>;
  destroy(): Promise<void>;
}

interface WebSrClass {
  new (params: {
    canvas: OffscreenCanvas;
    weights: unknown;
    network_name: string;
    gpu: unknown;
  }): WebSrInstance;
  initWebGPU(): Promise<unknown>;
}

interface WorkerScope {
  onmessage: ((event: MessageEvent<UpscaleRequest>) => void) | null;
  postMessage(message: UpscaleResponse): void;
  importScripts(...urls: string[]): void;
  WebSR?: WebSrClass;
}

const scope = self as unknown as WorkerScope;

scope.onmessage = async (event) => {
  const request = event.data;
  if (request?.type !== "upscale") return;

  try {
    scope.importScripts(request.websrUrl);
    const WebSR = scope.WebSR;
    if (!WebSR) {
      scope.postMessage({ type: "failed" });
      return;
    }

    const gpu = await WebSR.initWebGPU();
    console.info("[game-image-worker]", "initWebGPU", Boolean(gpu));
    if (!gpu) {
      scope.postMessage({ type: "unsupported" });
      return;
    }

    const { width, height } = upscaleDimensions(request.width, request.height);
    const canvas = new OffscreenCanvas(width, height);

    const websr = new WebSR({
      canvas,
      weights: request.weights,
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
