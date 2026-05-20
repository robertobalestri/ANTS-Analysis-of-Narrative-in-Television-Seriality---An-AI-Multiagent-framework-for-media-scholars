import React, { useState, useEffect } from 'react';
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
import { EventDrivenAnalysisDashboard } from './components/event_driven';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ApiClient } from './services/api/ApiClient';
import { isApiSuccess } from './architecture/types/api';
import { useWorkspaceStore } from './store/workspaceStore';
import { useDashboardStore } from './store/dashboardStore';

const App: React.FC = () => {
  const {
    explorerSeries,
    selectedSeries,
    activeSection,
    setSelectedSeries,
    setActiveSection,
    fetchExplorerSeries,
    refreshExplorerData,
    fetchCharacters
  } = useWorkspaceStore();

  const {
    episodes,
    arcs,
    libraryStatus,
    fetchDashboardData,
    refreshArcs
  } = useDashboardStore();

  const [newSeriesCode, setNewSeriesCode] = useState('');
  const [newSeriesName, setNewSeriesName] = useState('');
  const [isCreatingSeries, setIsCreatingSeries] = useState(false);
  const [explorerRefreshKey, setExplorerRefreshKey] = useState(0);

  // Initialize explorer
  useEffect(() => {
    const controller = new AbortController();
    void fetchExplorerSeries(controller.signal);
    return () => controller.abort();
  }, [fetchExplorerSeries]);

  // Fetch dashboard data and characters when selection changes
  useEffect(() => {
    if (!selectedSeries) return;
    const controller = new AbortController();
    void fetchDashboardData(selectedSeries, controller.signal);
    void fetchCharacters(selectedSeries, controller.signal);
    return () => controller.abort();
  }, [selectedSeries, fetchDashboardData, fetchCharacters]);

  const handleCreateSeries = async () => {
    if (!newSeriesCode || !newSeriesName) return;
    setIsCreatingSeries(true);
    const api = ApiClient.getInstance();
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

  const handleArcUpdated = () => {
    if (selectedSeries) {
      void refreshArcs(selectedSeries);
    }
  };

  const handleRefreshExplorer = async () => {
    await refreshExplorerData();
    setExplorerRefreshKey(k => k + 1);
  };

  const hasNarrativeData = arcs.length > 0;
  const emptyStateBg = useColorModeValue('white', 'gray.800');

  const renderActiveSection = () => {
    switch (activeSection) {
      case 'series-manager':
        return (
          <ErrorBoundary>
            <VStack spacing={4} align="stretch">
              <LibraryExplorer
                selectedSeries={selectedSeries}
                onSelectSeries={setSelectedSeries}
                onDataChange={(data) => useWorkspaceStore.getState().setExplorerSeries(data)}
                refreshKey={explorerRefreshKey}
              />
            </VStack>
          </ErrorBoundary>
        );

      case 'analysis-engine':
        return (
          <ErrorBoundary>
            <AnalysisEnginePanel
              seriesList={explorerSeries}
              selectedSeriesCode={selectedSeries}
              onSelectSeries={setSelectedSeries}
              onSelectSeriesManager={() => setActiveSection('series-manager')}
              onRefresh={handleRefreshExplorer}
            />
          </ErrorBoundary>
        );

      case 'event-driven-analysis':
        return (
          <ErrorBoundary>
            <EventDrivenAnalysisDashboard series={selectedSeries || ''} />
          </ErrorBoundary>
        );

      case 'settings':
        return (
          <ErrorBoundary>
            <SettingsPanel />
          </ErrorBoundary>
        );

      case 'visualization-dashboard':
        if (selectedSeries && (libraryStatus?.analysis_state === 'completed' || hasNarrativeData)) {
          return (
            <ErrorBoundary>
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
                        series={selectedSeries}
                        arcs={arcs}
                        episodes={episodes}
                        onArcUpdated={handleArcUpdated}
                      />
                    </TabPanel>
                    <TabPanel>
                      <VectorStoreTabManager
                        series={selectedSeries}
                        onArcUpdated={handleArcUpdated}
                      />
                    </TabPanel>
                    <TabPanel>
                      <CharacterManager
                        series={selectedSeries}
                        onCharacterUpdated={handleArcUpdated}
                      />
                    </TabPanel>
                  </TabPanels>
                </Tabs>
              </Box>
            </ErrorBoundary>
          );
        }
        break;
    }

    return (
      <Box textAlign="center" p={8} bg={emptyStateBg} borderRadius="lg" shadow="sm">
        <Text>
          {selectedSeries
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
                {([
                  { key: 'series-manager', label: 'Series Manager & File Upload' },
                  { key: 'analysis-engine', label: 'Analysis Engine' },
                  { key: 'visualization-dashboard', label: 'Narrative Arcs Dashboard' },
                  { key: 'event-driven-analysis', label: 'Event Driven Video Analysis' },
                  { key: 'settings', label: 'Settings' },
                ] as const).map(({ key, label }) => (
                  <Button
                    key={key}
                    variant={activeSection === key ? 'solid' : 'ghost'}
                    colorScheme={activeSection === key ? 'blue' : 'gray'}
                    onClick={() => setActiveSection(key)}
                    justifyContent="flex-start"
                    size="sm"
                  >
                    {label}
                  </Button>
                ))}
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
                        variant={selectedSeries === s.code ? 'solid' : 'ghost'}
                        colorScheme={selectedSeries === s.code ? 'blue' : 'gray'}
                        size="sm"
                        onClick={() => setSelectedSeries(s.code)}
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

            {selectedSeries && (
              <Box pt={4} mt="auto">
                {explorerSeries.find(s => s.code === selectedSeries)?.poster_url ? (
                  <Box borderRadius="md" overflow="hidden" shadow="sm" borderWidth="1px" mb={2}>
                    <img 
                      src={explorerSeries.find(s => s.code === selectedSeries)?.poster_url} 
                      alt="Series Poster"
                      style={{ width: '100%', height: 'auto', display: 'block' }}
                    />
                  </Box>
                ) : (
                  <Box p={2} bg="gray.100" borderRadius="md" textAlign="center" fontSize="xs" color="gray.400">
                    No Poster
                  </Box>
                )}
                <Text fontSize="xs" color="gray.500" textAlign="center">Selected: {selectedSeries}</Text>
              </Box>
            )}
          </VStack>
        </Box>

        <Box className={styles.mainContent}>
          <VStack spacing={4} align="stretch">
            <Box className={styles.header} bg={useColorModeValue('white', 'gray.800')}>
              <Heading className={styles.pageTitle}>ANTS Analysis of Narrative in Television Seriality</Heading>
            </Box>
            <Box px={4}>{renderActiveSection()}</Box>
          </VStack>
        </Box>
      </Box>
    </Box>
  );
};

export default App;