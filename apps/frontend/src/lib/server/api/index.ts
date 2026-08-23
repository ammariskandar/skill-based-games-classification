export { getJSON, postJSON } from "./client";
export { apiError } from "./errors";
export {
  BackendApiError,
  GameNotFoundError,
  getGameCatalogue,
  getGameDetail,
  getHomepageCarousel,
} from "./games";
export type {
  ClassificationProfile,
  ClassificationRegime,
  GameCatalogueClassification,
  GameCatalogueItem,
  GameCatalogueQuery,
  GameCatalogueResponse,
  GameDetailGame,
  GameDetailResponse,
  GameFinalClassification,
  GameSource,
  HomepageCarouselCard,
  HomepageCarouselResponse,
} from "./games";
export type {
  ApiError,
  ApiFailure,
  ApiNoContent,
  ApiResult,
  ApiSuccess,
  ErrorCode,
  GetOptions,
  PostOptions,
  RequestOptions,
} from "./types";
