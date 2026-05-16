/* Unique arc types — shared types re-exported from shared/ */
export { ArcType } from 'shared/types';
import type { NarrativeArc, ArcProgression, ApiResponse } from 'shared/types';
export type { NarrativeArc, ArcProgression, ApiResponse };

export interface ArcCluster {
  cluster_id: number;
  arcs: Array<{
    id: string;
    title: string;
    type: string;
    metadata: Record<string, unknown>;
    cluster_probability: number;
    embedding?: number[];
  }>;
  average_distance: number;
  size: number;
  average_probability: number;
  cluster_persistence?: number;
}

export interface ProgressionMapping {
  season: string;
  episode: string;
  content: string;
  interfering_characters: string[];
  arc_id?: string;
  arc_title?: string;
  series?: string;
}

export interface CreateArcData extends Omit<Partial<NarrativeArc>, 'progressions'> {
  progressions?: Omit<Partial<ArcProgression>, 'id'>[];
}