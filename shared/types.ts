/* Shared types for ANTS API — consumed by frontend (TS) and backend (Pydantic) */

export enum ArcType {
  SoapArc = 'Soap Arc',
  GenreSpecificArc = 'Genre-Specific Arc',
  AnthologyArc = 'Anthology Arc'
}

export interface ArcProgression {
  id: string;
  content: string;
  series: string;
  season: string;
  episode: string;
  ordinal_position: number;
  interfering_characters: string[];
}

export interface NarrativeArc {
  id: string;
  title: string;
  description: string;
  arc_type: ArcType;
  main_characters: string[];
  series: string;
  progressions: ArcProgression[];
}

export interface Character {
  entity_name: string;
  best_appellation: string;
  series: string;
  appellations: string[];
}

export interface Episode {
  season: string;
  episode: string;
}

export interface LibrarySeriesSummary {
  code: string;
  display_name: string;
  analysis_state: 'idle' | 'ready' | 'running' | 'completed' | 'failed';
  expected_episode_count: number;
  uploaded_episode_count: number;
  unmatched_upload_count: number;
}

export interface LibraryEpisodeStatus {
  season: string;
  episode: string;
  has_plot: boolean;
}

export interface LibraryUpload {
  upload_id: string;
  filename: string;
}

export interface LibrarySeriesStatus extends LibrarySeriesSummary {
  episodes: LibraryEpisodeStatus[];
  unmatched_uploads: LibraryUpload[];
  auto_matched_uploads?: Array<{
    season: string;
    episode: string;
    path: string;
  }>;
}

export interface ExplorerEpisodeStatus {
  series: string;
  season: string;
  episode: string;
  has_plot_file: boolean;
  has_srt_file: boolean;
  has_video_file: boolean;
  video_filename?: string;
  has_dialogue_json: boolean;
  has_analysis_artifacts: boolean;
  has_clips: boolean;
  progression_count: number;
  analysis_status: 'completed' | 'error' | 'pending' | 'not_processed' | 'missing_files';
}

export interface ExplorerSeason {
  season: string;
  episodes: ExplorerEpisodeStatus[];
}

export interface ExplorerSeries {
  code: string;
  display_name: string;
  poster_url?: string;
  seasons?: ExplorerSeason[];
}

export interface VectorStoreEntry {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  embedding?: number[];
  distance?: number;
}

export interface ApiErrorResponse {
  error: string;
  code?: string;
  details?: Record<string, unknown>;
}

export interface ApiSuccessResponse<T> {
  data: T;
  meta?: {
    total?: number;
    page?: number;
    limit?: number;
  };
}

export type ApiResponse<T> = ApiSuccessResponse<T> | ApiErrorResponse;

export function isApiError<T>(res: ApiResponse<T>): res is ApiErrorResponse {
  return 'error' in res;
}

export function isApiSuccess<T>(res: ApiResponse<T>): res is ApiSuccessResponse<T> {
  return 'data' in res;
}