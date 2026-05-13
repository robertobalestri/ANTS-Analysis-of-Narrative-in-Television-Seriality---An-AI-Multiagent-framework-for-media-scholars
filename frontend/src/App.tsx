import React, { useReducer, useState, useEffect } from 'react';
import {
  Box,
  VStack,
  Heading,
  Text,
  Button,
  useColorModeValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Divider,
  Input,
} from '@chakra-ui/react';
import styles from '@/styles/components/Layout.module.css';
import { NarrativeArcManager } from './components/narrative/NarrativeArcManager';
import { VectorStoreTabManager } from './components/vector/VectorStoreTabManager';
import { CharacterManager } from './components/character/CharacterManager';
import { AnalysisEnginePanel } from './components/analysis/AnalysisEnginePanel';
import { LibraryExplorer } from './components/library/LibraryExplorer';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ApiClient, type RequestOptions } from './services/api/ApiClient';
import { isApiSuccess } from './architecture/types/api';
import type { NarrativeArc, Episode, LibrarySeriesStatus, ExplorerSeries } from './architecture/types';


type WorkspaceSection = 'series-manager' | 'analysis-engine' | 'visualization-dashboard' | 'settings';

// --- Consolidated state for series selection across sections ---
interface SeriesSelectionState {
  /** Global series selected in the sidebar */
  selectedSeries: string;
}

const initialSeriesSelection: SeriesSelectionState = {
  selectedSeries: '',
};

type SeriesSelectionAction =
  | { type: 'SET_SELECTED_SERIES'; payload: string };

function seriesSelectionReducer(
  state: SeriesSelectionState,
  action: SeriesSelectionAction,
): SeriesSelectionState {
  switch (action.type) {
    case 'SET_SELECTED_SERIES':
      return { ...state, selectedSeries: action.payload };
    default:
      return state;
  }
}

// --- Consolidated state for dashboard data ---
interface DashboardDataState {
  episodes: Episode[];
  arcs: NarrativeArc[];
  knownSeries: string[];
  libraryStatus: LibrarySeriesStatus | null;
}

const initialDashboardData: DashboardDataState = {
  episodes: [],
  arcs: [],
  knownSeries: [],
  libraryStatus: null,
};

type DashboardDataAction =
  | { type: 'SET_EPISODES'; payload: Episode[] }
  | { type: 'SET_ARCS'; payload: NarrativeArc[] }
  | { type: 'SET_KNOWN_SERIES'; payload: string[] }
  | { type: 'SET_LIBRARY_STATUS'; payload: LibrarySeriesStatus | null }
  | { type: 'CLEAR_DASHBOARD' };

function dashboardDataReducer(
  state: DashboardDataState,
  action: DashboardDataAction,
): DashboardDataState {
  switch (action.type) {
    case 'SET_EPISODES':
      return { ...state, episodes: action.payload };
    case 'SET_ARCS':
      return { ...state, arcs: action.payload };
    case 'SET_KNOWN_SERIES':
      return { ...state, knownSeries: action.payload };
    case 'SET_LIBRARY_STATUS':
      return { ...state, libraryStatus: action.payload };
    case 'CLEAR_DASHBOARD':
      return { ...state, episodes: [], arcs: [] };
    default:
      return state;
  }
}

const api = new ApiClient();

const App: React.FC = () => {
  const [seriesSelection, dispatchSeries] = useReducer(seriesSelectionReducer, initialSeriesSelection);
  const [dashboardData, dispatchDashboard] = useReducer(dashboardDataReducer, initialDashboardData);
  const [explorerSeries, setExplorerSeries] = useState<ExplorerSeries[]>([]);
  const [explorerRefreshKey, setExplorerRefreshKey] = useState(0);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>('series-manager');
  const [newSeriesCode, setNewSeriesCode] = useState('');
  const [newSeriesName, setNewSeriesName] = useState('');
  const [isCreatingSeries, setIsCreatingSeries] = useState(false);

  const fetchExplorerSeries = async (signal?: AbortSignal) => {
    try {
      const response = await api.request<ExplorerSeries[]>('/library/explorer', { signal });
      if (isApiSuccess<ExplorerSeries[]>(response)) {
        setExplorerSeries(response.data);
        const codes = response.data.map(s => s.code);
        dispatchDashboard({ type: 'SET_KNOWN_SERIES', payload: codes });
        
        // Default selection if none
        if (!seriesSelection.selectedSeries && response.data.length > 0) {
          dispatchSeries({ type: 'SET_SELECTED_SERIES', payload: response.data[0].code });
        }
      }
    } catch (error) {
      console.error('Error fetching explorer series:', error);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    void fetchExplorerSeries(controller.signal);
    return () => controller.abort();
  }, []);

  const handleCreateSeries = async () => {
    if (!newSeriesCode || !newSeriesName) return;
    setIsCreatingSeries(true);
    try {
      const response = await api.createLibrarySeries(newSeriesCode, newSeriesName);
      if (isApiSuccess(response)) {
        setNewSeriesCode('');
        setNewSeriesName('');
        await fetchExplorerSeries();
      }
    } finally {
      setIsCreatingSeries(false);
    }
  };

  // Fetch data when the selected series changes
  useEffect(() => {
    if (!seriesSelection.selectedSeries) {
      return;
    }

    const controller = new AbortController();
    const options: RequestOptions = { signal: controller.signal };

    const fetchData = async () => {
      try {
        const [episodesResponse, arcsResponse] = await Promise.all([
          api.request<Episode[]>(`/episodes/${seriesSelection.selectedSeries}`, options),
          api.getArcs(seriesSelection.selectedSeries, options)
        ]);

        if (isApiSuccess<Episode[]>(episodesResponse)) {
          dispatchDashboard({ type: 'SET_EPISODES', payload: episodesResponse.data });
        }
        if (isApiSuccess<NarrativeArc[]>(arcsResponse)) {
          dispatchDashboard({ type: 'SET_ARCS', payload: arcsResponse.data });
        }
      } catch (error) {
        console.error('Error fetching data:', error);
        dispatchDashboard({ type: 'CLEAR_DASHBOARD' });
      }
    };

    void fetchData();

    return () => controller.abort();
  }, [seriesSelection.selectedSeries]);

  const handleArcUpdated = async () => {
    if (seriesSelection.selectedSeries) {
      try {
        const response = await api.request<NarrativeArc[]>(`/arcs/series/${seriesSelection.selectedSeries}`);
        if (isApiSuccess<NarrativeArc[]>(response)) {
          dispatchDashboard({ type: 'SET_ARCS', payload: response.data });
        }
      } catch (error) {
        console.error('Error refreshing arcs:', error);
      }
    }
  };

  const hasNarrativeData = dashboardData.arcs.length > 0;
  const emptyStateBg = useColorModeValue('white', 'gray.800');

  const refreshExplorerData = async () => {
    const response = await api.request<ExplorerSeries[]>('/library/explorer');
    if (isApiSuccess<ExplorerSeries[]>(response)) {
      setExplorerSeries(response.data);
    }
    setExplorerRefreshKey((current) => current + 1);
  };

  const renderActiveSection = () => {
    if (activeSection === 'series-manager') {
      return (
        <ErrorBoundary>
          <VStack spacing={4} align="stretch">
            <LibraryExplorer
              selectedSeries={seriesSelection.selectedSeries}
              onSelectSeries={(s) => dispatchSeries({ type: 'SET_SELECTED_SERIES', payload: s })}
              onDataChange={setExplorerSeries}
              refreshKey={explorerRefreshKey}
            />
          </VStack>
        </ErrorBoundary>
      );
    }

    if (activeSection === 'analysis-engine') {
      return (
        <ErrorBoundary>
          <AnalysisEnginePanel
            seriesList={explorerSeries}
            selectedSeriesCode={seriesSelection.selectedSeries}
            onSelectSeries={(s) => dispatchSeries({ type: 'SET_SELECTED_SERIES', payload: s })}
            onSelectSeriesManager={() => setActiveSection('series-manager')}
            onRefresh={refreshExplorerData}
          />
        </ErrorBoundary>
      );
    }

    if (activeSection === 'settings') {
      return (
        <ErrorBoundary>
          <SettingsPanel />
        </ErrorBoundary>
      );
    }

    if (seriesSelection.selectedSeries && (dashboardData.libraryStatus?.analysis_state === 'completed' || hasNarrativeData || (dashboardData.knownSeries.includes(seriesSelection.selectedSeries) && dashboardData.libraryStatus === null))) {
      return (
        <ErrorBoundary>
          <VStack spacing={4} align="stretch">
            <Box className={styles.tabContainer}>
              <Tabs isFitted variant="enclosed">
              <TabList>
                <Tab>Narrative Arcs Timeline</Tab>
                <Tab>Vector Store</Tab>
                <Tab>Characters</Tab>
              </TabList>
              <TabPanels>
                <TabPanel p={0}>
                  <NarrativeArcManager
                    series={seriesSelection.selectedSeries}
                    arcs={dashboardData.arcs}
                    episodes={dashboardData.episodes}
                    onArcUpdated={handleArcUpdated}
                  />
                </TabPanel>
                <TabPanel>
                  <VectorStoreTabManager
                    series={seriesSelection.selectedSeries}
                    onArcUpdated={handleArcUpdated}
                  />
                </TabPanel>
                <TabPanel>
                  <CharacterManager
                    series={seriesSelection.selectedSeries}
                    onCharacterUpdated={handleArcUpdated}
                  />
                </TabPanel>
              </TabPanels>
            </Tabs>
          </Box>
        </VStack>
        </ErrorBoundary>
      );
    }

    return (
      <Box textAlign="center" p={8} bg={emptyStateBg} borderRadius="lg" shadow="sm">
        <Text>
          {seriesSelection.selectedSeries
            ? 'Select a series with available narrative results to open the Visualization Dashboard.'
            : 'Create or select a series to start building the dataset.'}
        </Text>
      </Box>
    );
  };

  return (
    <Box className={styles.pageContainer} bg={useColorModeValue('gray.50', 'gray.900')}>
      <Box className={styles.appShell}>
        <Box className={styles.sidebar} bg={useColorModeValue('white', 'gray.800')} borderRightWidth="1px" p={4}>
          <VStack align="stretch" spacing={6} height="100%">
            <Box>
              <Heading size="xs" textTransform="uppercase" color="gray.500" mb={4}>Navigation</Heading>
              <VStack align="stretch" spacing={2}>
                <Button 
                  variant={activeSection === 'series-manager' ? 'solid' : 'ghost'} 
                  colorScheme={activeSection === 'series-manager' ? 'blue' : 'gray'}
                  onClick={() => setActiveSection('series-manager')}
                  justifyContent="flex-start"
                  size="sm"
                >
                  Series Manager
                </Button>
                <Button 
                  variant={activeSection === 'analysis-engine' ? 'solid' : 'ghost'} 
                  colorScheme={activeSection === 'analysis-engine' ? 'blue' : 'gray'}
                  onClick={() => setActiveSection('analysis-engine')}
                  justifyContent="flex-start"
                  size="sm"
                >
                  Analysis Engine
                </Button>
                <Button 
                  variant={activeSection === 'visualization-dashboard' ? 'solid' : 'ghost'} 
                  colorScheme={activeSection === 'visualization-dashboard' ? 'blue' : 'gray'}
                  onClick={() => setActiveSection('visualization-dashboard')}
                  justifyContent="flex-start"
                  size="sm"
                >
                  Visualization Dashboard
                </Button>
                <Button 
                  variant={activeSection === 'settings' ? 'solid' : 'ghost'} 
                  colorScheme={activeSection === 'settings' ? 'blue' : 'gray'}
                  onClick={() => setActiveSection('settings')}
                  justifyContent="flex-start"
                  size="sm"
                >
                  Settings
                </Button>
              </VStack>
            </Box>

            <Divider />

            <Box flex="1" overflowY="auto">
              <VStack align="stretch" spacing={4}>
                <Box>
                  <Heading size="xs" textTransform="uppercase" color="gray.500" mb={3}>Add Series</Heading>
                  <VStack spacing={2}>
                    <Input 
                      size="xs" 
                      placeholder="Code (e.g. B99)" 
                      value={newSeriesCode}
                      onChange={e => setNewSeriesCode(e.target.value)}
                    />
                    <Input 
                      size="xs" 
                      placeholder="Name" 
                      value={newSeriesName}
                      onChange={e => setNewSeriesName(e.target.value)}
                    />
                    <Button size="xs" width="100%" colorScheme="blue" onClick={handleCreateSeries} isLoading={isCreatingSeries}>
                      Add Series
                    </Button>
                  </VStack>
                </Box>

                <Divider />

                <Box>
                  <Heading size="xs" textTransform="uppercase" color="gray.500" mb={3}>Library</Heading>
                  <VStack align="stretch" spacing={2}>
                    {explorerSeries.map((s) => (
                      <Button
                        key={s.code}
                        variant={seriesSelection.selectedSeries === s.code ? 'solid' : 'ghost'}
                        colorScheme={seriesSelection.selectedSeries === s.code ? 'blue' : 'gray'}
                        size="sm"
                        onClick={() => dispatchSeries({ type: 'SET_SELECTED_SERIES', payload: s.code })}
                        justifyContent="flex-start"
                        width="100%"
                        px={2}
                      >
                        <Text isTruncated fontSize="xs">{s.display_name}</Text>
                      </Button>
                    ))}
                  </VStack>
                </Box>
              </VStack>
            </Box>

            {seriesSelection.selectedSeries && (
              <Box pt={4} mt="auto">
                {explorerSeries.find(s => s.code === seriesSelection.selectedSeries)?.poster_url ? (
                  <Box borderRadius="md" overflow="hidden" shadow="sm" borderWidth="1px" mb={2}>
                    <img 
                      src={explorerSeries.find(s => s.code === seriesSelection.selectedSeries)?.poster_url} 
                      alt="Series Poster"
                      style={{ width: '100%', height: 'auto', display: 'block' }}
                    />
                  </Box>
                ) : (
                  <Box p={2} bg="gray.100" borderRadius="md" textAlign="center" fontSize="xs" color="gray.400">
                    No Poster
                  </Box>
                )}
                <Text fontSize="xs" color="gray.500" textAlign="center">Selected: {seriesSelection.selectedSeries}</Text>
              </Box>
            )}
          </VStack>
        </Box>

        <Box className={styles.mainContent}>
          <VStack spacing={4} align="stretch">
            <Box className={styles.header} bg={useColorModeValue('white', 'gray.800')}>
              <Heading className={styles.pageTitle}>Narrative Arcs Dashboard</Heading>
            </Box>
            <Box px={4}>{renderActiveSection()}</Box>
          </VStack>
        </Box>
      </Box>
    </Box>
  );
};

export default App;