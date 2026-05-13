export interface ExplorerEpisodeStatus {
  series: string;
  season: string;
  episode: string;
  has_plot_file: boolean;
  has_srt_file: boolean;
  has_dialogue_json: boolean;
  has_analysis_artifacts: boolean;
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
