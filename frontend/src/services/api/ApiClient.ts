import type {
  ApiResponse,
  NarrativeArc,
  Character,
  VectorStoreEntry,
  ArcProgression,
  ArcCluster,
  CreateArcData,
  LibrarySeriesSummary,
  LibrarySeriesStatus
} from '@/architecture/types';
import { isApiError, isApiSuccess } from '@/architecture/types/api';
import { config } from '@/config/environment';

// Add interface for arc creation data
interface ArcCreateData extends Omit<Partial<NarrativeArc>, 'progressions' | 'main_characters'> {
  initial_progression?: {
    content: string;
    season: string;
    episode: string;
    interfering_characters: string;
  };
  main_characters: string;
}

interface GenerateProgressionResponse {
  content: string;
  interfering_characters: string[];
}

type GenerateProgressionResult = GenerateProgressionResponse | { content: null; error: string };

export type RequestOptions = RequestInit & {
  signal?: AbortSignal;
};

// Update the createProgression interface to match API expectations
interface CreateProgressionData {
  arc_id: string;
  content: string;
  series: string;
  season: string;
  episode: string;
  interfering_characters: string | string[];  // Accept either format
}

export class ApiClient {
  private static instance: ApiClient;
  private baseUrl: string;

  private constructor(baseUrl: string = config.apiUrl) {
    this.baseUrl = baseUrl;
  }

  public static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient();
    }
    return ApiClient.instance;
  }

  public async request<T>(endpoint: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    let retries = 0;
    const maxRetries = 2;
    const retryDelay = 1000;

    const performRequest = async (): Promise<ApiResponse<T>> => {
      try {
        const headers = new Headers(options.headers ?? {});
        if (!headers.has('Accept')) {
          headers.set('Accept', 'application/json');
        }
        if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
          headers.set('Content-Type', 'application/json');
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
          ...options,
          headers,
        });

        if (!response.ok) {
          let detail = `HTTP error! status: ${response.status}`;
          try {
            const errorBody = await response.json();
            if (typeof errorBody?.detail === 'string') {
              detail = errorBody.detail;
            }
          } catch {
            // Keep the generic HTTP status message when no JSON detail is available.
          }
          throw new Error(detail);
        }

        const data = await response.json();
        return { data };
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return { error: 'Request cancelled' };
        }

        if (retries < maxRetries && !(error instanceof DOMException && error.name === 'AbortError')) {
          retries++;
          await new Promise(resolve => setTimeout(resolve, retryDelay * retries));
          return performRequest();
        }

        return {
          error: error instanceof Error ? error.message : 'Unknown error occurred'
        };
      }
    };

    return performRequest();
  }

  async getLibrarySeries(options?: RequestOptions): Promise<ApiResponse<LibrarySeriesSummary[]>> {
    return this.request<LibrarySeriesSummary[]>('/library/series', options);
  }

  // DEPRECATED: use getLibrarySeries
  async getSeries(options?: RequestOptions): Promise<ApiResponse<string[]>> {
    const response = await this.getLibrarySeries(options);
    if (isApiSuccess<LibrarySeriesSummary[]>(response)) {
      return { data: response.data.map(s => s.code) };
    }
    return response as ApiResponse<string[]>;
  }

  async createLibrarySeries(code: string, displayName: string): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>('/library/series', {
      method: 'POST',
      body: JSON.stringify({ code, display_name: displayName }),
    });
  }

  async createLibrarySeasons(series: string, seasons: string[]): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/seasons`, {
      method: 'POST',
      body: JSON.stringify({ seasons }),
    });
  }

  async createLibraryEpisodes(series: string, season: string, episodes: string[]): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/${season}/episodes`, {
      method: 'POST',
      body: JSON.stringify({ episodes }),
    });
  }

  async uploadLibraryPlots(series: string, files: File[]): Promise<ApiResponse<LibrarySeriesStatus>> {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/uploads`, {
      method: 'POST',
      body: formData,
    });
  }

  async assignLibraryUpload(series: string, uploadId: string, season: string, episode: string): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/uploads/assign`, {
      method: 'POST',
      body: JSON.stringify({ upload_id: uploadId, season, episode }),
    });
  }

  async analyzeLibrarySeries(series: string): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/analyze`, {
      method: 'POST',
    });
  }

  async getLibrarySeriesStatus(series: string, options?: RequestOptions): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/status`, options);
  }

  async getEpisodePlot(series: string, season: string, episode: string, options?: RequestOptions): Promise<ApiResponse<{ content: string }>> {
    return this.request<{ content: string }>(`/library/series/${series}/${season}/${episode}/plot`, options);
  }

  getEpisodeVideoUrl(series: string, season: string, episode: string): string {
    return `${this.baseUrl}/library/series/${series}/${season}/${episode}/video`;
  }

  async deleteEpisodeFile(series: string, season: string, episode: string, fileType: string): Promise<ApiResponse<LibrarySeriesStatus>> {
    return this.request<LibrarySeriesStatus>(`/library/series/${series}/${season}/${episode}/file/${fileType}`, {
      method: 'DELETE',
    });
  }

  async analyzeVideoScenes(series: string, season: string, episode: string): Promise<ApiResponse<{ status: string; message: string; scenes: any[] }>> {
    return this.request<{ status: string; message: string; scenes: any[] }>(`/library/series/${series}/${season}/${episode}/analyze-video`, {
      method: 'POST',
    });
  }

  async transcribeVideo(series: string, season: string, episode: string): Promise<ApiResponse<{ status: string; message: string; srt_path: string }>> {
    return this.request<{ status: string; message: string; srt_path: string }>(`/library/series/${series}/${season}/${episode}/transcribe-video`, {
      method: 'POST',
    });
  }

  async generatePlotFromSrt(series: string, season: string, episode: string): Promise<ApiResponse<{ status: string; message: string; plot_path: string }>> {
    return this.request<{ status: string; message: string; plot_path: string }>(`/library/series/${series}/${season}/${episode}/plot-from-srt`, {
      method: 'POST',
    });
  }

  async fullVideoToPlot(series: string, season: string, episode: string): Promise<ApiResponse<{ status: string; message: string; plot_path: string }>> {
    return this.request<{ status: string; message: string; plot_path: string }>(`/library/series/${series}/${season}/${episode}/full-video-to-plot`, {
      method: 'POST',
    });
  }

  // Arc endpoints
  async getArcs(series: string, options?: RequestOptions): Promise<ApiResponse<NarrativeArc[]>> {
    return this.request<NarrativeArc[]>(`/arcs/series/${series}`, options);
  }

  async getArcById(arcId: string, options?: RequestOptions): Promise<ApiResponse<NarrativeArc>> {
    return this.request<NarrativeArc>(`/arcs/by-id/${arcId}`, options);
  }

  async createArc(arcData: CreateArcData): Promise<ApiResponse<NarrativeArc>> {
    console.log('Received arcData with progressions:', arcData.progressions?.length);

    // Validate required fields
    if (!arcData.title || !arcData.description || !arcData.arc_type || !arcData.series) {
      console.error('Missing required fields:', {
        hasTitle: !!arcData.title,
        hasDescription: !!arcData.description,
        hasArcType: !!arcData.arc_type,
        hasSeries: !!arcData.series
      });
      throw new Error('Missing required fields');
    }

    // Validate and format main_characters
    const mainCharacters = Array.isArray(arcData.main_characters)
      ? arcData.main_characters.join(';')
      : typeof arcData.main_characters === 'string'
        ? arcData.main_characters
        : '';

    console.log('Formatted main_characters:', mainCharacters);

    // If we have multiple progressions, use the first one as initial_progression
    let initialProgression: ArcCreateData['initial_progression'] | undefined;
    
    if (arcData.progressions?.[0]) {
      const firstProgression = arcData.progressions[0];
      console.log('Using first progression as initial progression:', firstProgression);

      if (firstProgression.content && firstProgression.season && firstProgression.episode) {
        initialProgression = {
          content: firstProgression.content,
          season: firstProgression.season,
          episode: firstProgression.episode,
          interfering_characters: Array.isArray(firstProgression.interfering_characters)
            ? firstProgression.interfering_characters.join(';')
            : firstProgression.interfering_characters || ''
        };
      }
    }

    const formattedData: ArcCreateData = {
      title: arcData.title,
      description: arcData.description,
      arc_type: arcData.arc_type,
      main_characters: mainCharacters,
      series: arcData.series,
      initial_progression: initialProgression
    };

    console.log('Sending formatted data to API:', formattedData);

    // Create the arc with initial progression
    const response = await this.request<NarrativeArc>('/arcs', {
      method: 'POST',
      body: JSON.stringify(formattedData),
    });

    // Check for error response
    if (isApiError(response)) {
      return response;
    }

    // If we have more progressions, add them to the created arc
    if (arcData.progressions && arcData.progressions.length > 1) {
      console.log(`Adding ${arcData.progressions.length - 1} additional progressions`);
      
      // Add remaining progressions
      for (let i = 1; i < arcData.progressions.length; i++) {
        const prog = arcData.progressions[i];
        
        // Skip if missing required fields
        if (!prog.content || !prog.season || !prog.episode) {
          console.warn('Skipping progression with missing required fields:', prog);
          continue;
        }

        await this.createProgression({
          arc_id: response.data.id,
          content: prog.content,
          series: prog.series || arcData.series,
          season: prog.season,
          episode: prog.episode,
          interfering_characters: Array.isArray(prog.interfering_characters)
            ? prog.interfering_characters.join(';')
            : ''
        });
      }
    }

    return response;
  }

  async updateArc(
    arcId: string,
    updateData: {
      title?: string;
      description?: string;
      arc_type?: string;
      main_characters?: string[] | string;
    }
  ): Promise<ApiResponse<NarrativeArc>> {
    const formattedData = {
      ...updateData,
      main_characters: typeof updateData.main_characters === 'string'
        ? (updateData.main_characters as string).split(';')
        : updateData.main_characters
    };

    return this.request<NarrativeArc>(
      `/arcs/${arcId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(formattedData)
      }
    );
  }

  async deleteArc(arcId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/arcs/${arcId}`, {
      method: 'DELETE',
    });
  }

  async mergeArcs(
    arc1Id: string,
    arc2Id: string,
    mergedData: Partial<NarrativeArc>
  ): Promise<ApiResponse<NarrativeArc>> {
    return this.request<NarrativeArc>('/arcs/merge', {
      method: 'POST',
      body: JSON.stringify({
        arc_id_1: arc1Id,
        arc_id_2: arc2Id,
        ...mergedData,
      }),
    });
  }

  // Character endpoints
  async getCharacters(series: string, options?: RequestOptions): Promise<ApiResponse<Character[]>> {
    return this.request<Character[]>(`/characters/${series}`, options);
  }

  async createCharacter(series: string, characterData: Partial<Character>): Promise<ApiResponse<Character>> {
    return this.request<Character>(`/characters/${series}`, {
      method: 'POST',
      body: JSON.stringify(characterData),
    });
  }

  async updateCharacter(series: string, characterData: Partial<Character>): Promise<ApiResponse<Character>> {
    return this.request<Character>(`/characters/${series}`, {
      method: 'PATCH',
      body: JSON.stringify(characterData),
    });
  }

  async deleteCharacter(series: string, entityName: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/characters/${series}/${entityName}`, {
      method: 'DELETE',
    });
  }

  async mergeCharacters(
    series: string,
    data: {
      character1_id: string;
      character2_id: string;
      keep_character: 'character1' | 'character2';
    }
  ): Promise<ApiResponse<void>> {
    return this.request<void>(`/characters/${series}/merge`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Vector store endpoints
  async searchVectorStore(
    series: string,
    query?: string,
    options?: RequestOptions
  ): Promise<ApiResponse<VectorStoreEntry[]>> {
    const endpoint = query
      ? `/vector-store/${series}?query=${encodeURIComponent(query)}`
      : `/vector-store/${series}`;
    return this.request<VectorStoreEntry[]>(endpoint, options);
  }

  async getArcClusters(
    series: string,
    params: {
      threshold?: number;
      min_cluster_size?: number;
      max_clusters?: number;
    } = {},
    options?: RequestOptions
  ): Promise<ApiResponse<ArcCluster[]>> {
    const queryParams = new URLSearchParams();
    if (params.threshold) queryParams.append('threshold', params.threshold.toString());
    if (params.min_cluster_size) queryParams.append('min_cluster_size', params.min_cluster_size.toString());
    if (params.max_clusters) queryParams.append('max_clusters', params.max_clusters.toString());

    const endpoint = `/vector-store/${series}/clusters${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return this.request<ArcCluster[]>(endpoint, options);
  }

  async compareArcs(arcIds: string[]): Promise<ApiResponse<{ distance: number }>> {
    return this.request<{ distance: number }>('/vector-store/compare', {
      method: 'POST',
      body: JSON.stringify(arcIds),
    });
  }

  async updateProgression(progressionId: string, data: Partial<ArcProgression>): Promise<ApiResponse<ArcProgression>> {
    const formattedData = {
      content: data.content,
      interfering_characters: data.interfering_characters || []
    };

    return this.request<ArcProgression>(`/progressions/${progressionId}`, {
      method: 'PATCH',
      body: JSON.stringify(formattedData),
    });
  }

  async createProgression(data: CreateProgressionData): Promise<ApiResponse<ArcProgression>> {
    // Format the data before sending
    const formattedData = {
      ...data,
      interfering_characters: Array.isArray(data.interfering_characters)
        ? data.interfering_characters.join(';')
        : data.interfering_characters
    };

    return this.request<ArcProgression>('/progressions', {
      method: 'POST',
      body: JSON.stringify(formattedData),
    });
  }

  async deleteProgression(progressionId: string): Promise<ApiResponse<void>> {
    return this.request<void>(
      `/progressions/${progressionId}`,
      {
        method: 'DELETE'
      }
    );
  }

  async generateProgression(
    arcId: string | null,
    series: string,
    season: string,
    episode: string,
    title?: string,
    description?: string
  ): Promise<GenerateProgressionResult> {
    try {
      const response = await this.request<GenerateProgressionResponse>(
        `/progressions/generate?series=${series}&season=${season}&episode=${episode}`,
        {
          method: 'POST',
          body: JSON.stringify({
            arc_id: arcId,
            arc_title: title || null,
            arc_description: description || null,
            delete_existing: true
          }),
        }
      );

      if (isApiError(response)) {
        console.error('Generation error:', response.error);
        return {
          content: null,
          error: response.error
        };
      }

      if (response.data.content === "NO_PROGRESSION") {
        return {
          content: null,
          error: "No progression found for this arc in this episode"
        };
      }

      if (!response.data.content) {
        return {
          content: null,
          error: "Failed to generate progression content"
        };
      }

      return {
        content: response.data.content,
        interfering_characters: response.data.interfering_characters || []
      };
    } catch (error) {
      console.error('Generation error:', error);
      return {
        content: null,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }
}
 