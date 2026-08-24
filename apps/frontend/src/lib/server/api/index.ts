export { getJSON, postJSON } from "./client";
export { apiError } from "./errors";
export {
  BackendApiError,
  GameNotFoundError,
  getGameCatalogue,
  getGameDetail,
  getGameSearchIndex,
  getHomepageCarousel,
} from "./games";
export type {
  CatalogueDominant,
  CatalogueProfile,
  CatalogueSort,
  ClassificationProfile,
  ClassificationRegime,
  GameCatalogueClassification,
  GameCatalogueItem,
  GameCatalogueQuery,
  GameCatalogueResponse,
  GameDetailGame,
  GameDetailResponse,
  GameFinalClassification,
  GameSearchIndexItem,
  GameSearchIndexResponse,
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
