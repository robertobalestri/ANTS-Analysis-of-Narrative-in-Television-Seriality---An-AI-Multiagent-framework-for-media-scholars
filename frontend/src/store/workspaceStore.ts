import { create } from 'zustand';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import type { ExplorerSeries, WorkspaceSection, Character } from '@/architecture/types';

interface WorkspaceState {
  // Data
  explorerSeries: ExplorerSeries[];
  selectedSeries: string;
  activeSection: WorkspaceSection;
  characters: Character[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setExplorerSeries: (series: ExplorerSeries[]) => void;
  setSelectedSeries: (seriesCode: string) => void;
  setActiveSection: (section: WorkspaceSection) => void;
  setCharacters: (characters: Character[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;

  // Async Actions
  fetchExplorerSeries: (signal?: AbortSignal) => Promise<void>;
  refreshExplorerData: () => Promise<void>;
  fetchCharacters: (series: string, signal?: AbortSignal) => Promise<void>;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  // Initial State
  explorerSeries: [],
  selectedSeries: '',
  activeSection: 'series-manager',
  characters: [],
  isLoading: false,
  error: null,

  // Simple Actions
  setExplorerSeries: (explorerSeries) => set({ explorerSeries }),
  setSelectedSeries: (selectedSeries) => set({ selectedSeries }),
  setActiveSection: (activeSection) => set({ activeSection }),
  setCharacters: (characters) => set({ characters }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),

  // Async Actions
  fetchExplorerSeries: async (signal?: AbortSignal) => {
    const api = ApiClient.getInstance();
    set({ isLoading: true, error: null });
    try {
      const response = await api.request<ExplorerSeries[]>('/library/explorer', { signal });
      if (isApiSuccess<ExplorerSeries[]>(response)) {
        set({ explorerSeries: response.data });
        
        // Default selection if none exists
        if (!get().selectedSeries && response.data.length > 0) {
          set({ selectedSeries: response.data[0].code });
        }
      } else {
        set({ error: response.error });
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      set({ error: err instanceof Error ? err.message : 'Failed to fetch series' });
    } finally {
      set({ isLoading: false });
    }
  },

  refreshExplorerData: async () => {
    const api = ApiClient.getInstance();
    try {
      const response = await api.request<ExplorerSeries[]>('/library/explorer');
      if (isApiSuccess<ExplorerSeries[]>(response)) {
        set({ explorerSeries: response.data });
      }
    } catch (err) {
      console.error('Error refreshing explorer data:', err);
    }
  },

  fetchCharacters: async (series: string, signal?: AbortSignal) => {
    if (!series) return;
    const api = ApiClient.getInstance();
    try {
      const response = await api.getCharacters(series, { signal });
      if (isApiSuccess<Character[]>(response)) {
        set({ characters: response.data });
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      console.error('Error fetching characters:', err);
    }
  },
}));
