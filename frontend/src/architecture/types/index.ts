/* Barrel export — types from shared/ via individual type files */
export { ArcType } from 'shared/types';
export type {
  ArcProgression,
  NarrativeArc,
  ArcCluster,
  ProgressionMapping,
  CreateArcData,
} from './arc';

export type { ApiResponse } from './api';
export type { Character } from './character';
export type { Episode } from './episode';

export type { VectorStoreEntry } from './vector';

export type {
  LibrarySeriesSummary,
  LibrarySeriesStatus,
  LibraryEpisodeStatus,
  LibraryUpload,
  ExplorerSeries,
  ExplorerSeason,
  ExplorerEpisodeStatus
} from './library';
export type { WorkspaceSection } from './workspace';

export type {
  NarrativeEvent,
  ArcInfo,
  EventDrivenAnalysisSnapshot,
  AnalyzeResult
} from './event_driven';