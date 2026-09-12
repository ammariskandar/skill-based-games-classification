export { getJSON, postJSON } from "./client";
export { apiError } from "./errors";
export {
  BackendApiError,
  GameNotFoundError,
  getGameCatalogue,
  getGameDetail,
  getGameRankings,
  getGameSearchIndex,
  getHomepageCarousel,
  getSimilarGames,
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
  RankingDimension,
  RankingDirection,
  RankingItem,
  RankingProfile,
  RankingQuery,
  RankingResponse,
  SimilarGameItem,
  SimilarGamesResponse,
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
export { getUserProfile, UserNotFoundError } from "./users";
export type {
  ProfileScoresDto,
  PublicUserProfileDto,
  TopGameDto,
  UserProfileOptions,
} from "./users";
export {
  QuestionnaireApiError,
  getQuestionnaireSession,
  submitQuestionnaire,
} from "./questionnaire";
export { submitManualScore } from "./score-submission";
export type {
  ManualScoreSubmissionRequest,
  ManualScoreSubmissionResponse,
  ManualScoreSubmissionResult,
} from "./score-submission";
export type {
  QuestionnaireRequestOptions,
  SubmitQuestionnaireResult,
} from "./questionnaire";
