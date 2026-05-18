export interface ArcInfo {
  id: string;
  title: string;
  color: string;
}

export interface NarrativeEvent {
  id: string;
  episode_ref: string;
  content: string;
  characters: string[];
  event_type: string;
  srt_start_index: number;
  srt_end_index: number;
  srt_start_time: string;
  srt_end_time: string;
  video_start?: number;
  video_end?: number;
  clip_path?: string;
  arc_ids?: string[];
  metadata?: Record<string, unknown>;
  created_at?: string;
}

export interface EventDrivenAnalysisSnapshot {
  series: string;
  events: NarrativeEvent[];
  active_terminal_nodes: string[];
  arcs: ArcInfo[];
  created_at?: string;
}

export interface AnalyzeResult {
  episode_ref: string;
  events_extracted: number;
  active_terminal_nodes: string[];
}