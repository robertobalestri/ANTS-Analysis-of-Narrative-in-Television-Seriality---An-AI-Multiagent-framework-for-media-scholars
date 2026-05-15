import { create } from 'zustand';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import type { Episode, NarrativeArc, LibrarySeriesStatus } from '@/architecture/types';

interface DashboardState {
  // Data
  episodes: Episode[];
  arcs: NarrativeArc[];
  knownSeries: string[];
  libraryStatus: LibrarySeriesStatus | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setEpisodes: (episodes: Episode[]) => void;
  setArcs: (arcs: NarrativeArc[]) => void;
  setKnownSeries: (series: string[]) => void;
  setLibraryStatus: (status: LibrarySeriesStatus | null) => void;
  clearDashboard: () => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;

  // Async Actions
  fetchDashboardData: (series: string, signal?: AbortSignal) => Promise<void>;
  refreshArcs: (series: string) => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // Initial State
  episodes: [],
  arcs: [],
  knownSeries: [],
  libraryStatus: null,
  isLoading: false,
  error: null,

  // Simple Actions
  setEpisodes: (episodes) => set({ episodes }),
  setArcs: (arcs) => set({ arcs }),
  setKnownSeries: (knownSeries) => set({ knownSeries }),
  setLibraryStatus: (libraryStatus) => set({ libraryStatus }),
  clearDashboard: () => set({ episodes: [], arcs: [], libraryStatus: null }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),

  // Async Actions
  fetchDashboardData: async (series: string, signal?: AbortSignal) => {
    if (!series) return;
    
    const api = ApiClient.getInstance();
    set({ isLoading: true, error: null });
    
    try {
      const [episodesResponse, arcsResponse, statusResponse] = await Promise.all([
        api.request<Episode[]>(`/episodes/${series}`, { signal }),
        api.getArcs(series, { signal }),
        api.getLibrarySeriesStatus(series, { signal })
      ]);

      if (isApiSuccess<Episode[]>(episodesResponse)) {
        set({ episodes: episodesResponse.data });
      }
      if (isApiSuccess<NarrativeArc[]>(arcsResponse)) {
        set({ arcs: arcsResponse.data });
      }
      if (isApiSuccess<LibrarySeriesStatus>(statusResponse)) {
        set({ libraryStatus: statusResponse.data });
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      console.error('Error fetching dashboard data:', err);
      set({ error: err instanceof Error ? err.message : 'Failed to fetch dashboard data' });
      get().clearDashboard();
    } finally {
      set({ isLoading: false });
    }
  },

  refreshArcs: async (series: string) => {
    if (!series) return;
    const api = ApiClient.getInstance();
    try {
      const response = await api.getArcs(series);
      if (isApiSuccess<NarrativeArc[]>(response)) {
        set({ arcs: response.data });
      }
    } catch (err) {
      console.error('Error refreshing arcs:', err);
    }
  },
}));
