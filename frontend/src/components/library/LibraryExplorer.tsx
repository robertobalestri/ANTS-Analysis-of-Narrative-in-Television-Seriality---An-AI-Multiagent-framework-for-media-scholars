import React, { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Divider,
  HStack,
  Input,
  SimpleGrid,
  Spinner,
  Text,
  Textarea,
  VStack,
  useToast,
  IconButton,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import { formatSeasonCode, formatEpisodeCode } from '@/utils/formatters';

import type { ExplorerEpisodeStatus, ExplorerSeries } from '@/architecture/types';
import { isApiError } from '@/architecture/types/api';

interface LibraryExplorerProps {
  selectedSeries: string;
  onSelectSeries: (series: string) => void;
  onDataChange?: (series: ExplorerSeries[]) => void;
  refreshKey?: number;
  onSelectAnalysisEngine?: () => void;
}


const api = new ApiClient();

export const LibraryExplorer: React.FC<LibraryExplorerProps> = ({
  selectedSeries,
  onSelectSeries,
  onDataChange,
  refreshKey,
}) => {
  const toast = useToast();
  const [series, setSeries] = useState<ExplorerSeries[]>([]);
  const [selectedEpisode, setSelectedEpisode] = useState<ExplorerEpisodeStatus | null>(null);
  const [, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [newSeasonBySeries, setNewSeasonBySeries] = useState<Record<string, string>>({});
  const [newEpisodeBySeason, setNewEpisodeBySeason] = useState<Record<string, string>>({});
  const [plotContent, setPlotContent] = useState<string>('');
  const [isFetchingPlot, setIsFetchingPlot] = useState(false);

  const selectedSeriesData = useMemo(
    () => series.find((item) => item.code === selectedSeries) ?? null,
    [selectedSeries, series]
  );

  const refreshExplorer = async (signal?: AbortSignal) => {
    setIsLoading(true);
    setIsRefreshing(true);

    try {
      const response = await api.request<ExplorerSeries[]>('/library/explorer', { signal });

      if (!isApiSuccess<ExplorerSeries[]>(response)) {
        if (response.error !== 'Request cancelled') {
          toast({ title: 'Unable to load library explorer', description: response.error, status: 'error' });
        }
        return;
      }

      setSeries(response.data);
      onDataChange?.(response.data);
      if (!selectedSeries && response.data[0]) {
        onSelectSeries(response.data[0].code);
      }
      return response.data;
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    void refreshExplorer(controller.signal);
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => {
    if (!selectedSeriesData || !selectedEpisode) {
      setPlotContent('');
      return;
    }

    if (selectedEpisode.series !== selectedSeries) {
      setSelectedEpisode(null);
      setPlotContent('');
      return;
    }

    if (selectedEpisode.has_plot_file) {
      void fetchPlotContent(selectedEpisode.series, selectedEpisode.season, selectedEpisode.episode);
    } else {
      setPlotContent('');
    }
  }, [
    selectedEpisode?.series,
    selectedEpisode?.season,
    selectedEpisode?.episode,
    selectedEpisode?.has_plot_file,
    selectedSeries,
    selectedSeriesData
  ]);

  const fetchPlotContent = async (seriesCode: string, seasonCode: string, episodeCode: string) => {
    setPlotContent(''); // Clear previous content
    setIsFetchingPlot(true);
    try {
      const response = await api.getEpisodePlot(seriesCode, seasonCode, episodeCode);
      if (isApiSuccess(response)) {
        setPlotContent(response.data.content);
      } else {
        toast({
          title: 'Unable to load plot text',
          description: response.error,
          status: 'warning',
          duration: 3000,
          isClosable: true,
        });
      }
    } finally {
      setIsFetchingPlot(false);
    }
  };

  const handleAddSeason = async (seriesCode: string) => {
    const seasonValue = newSeasonBySeries[seriesCode]?.trim();
    if (!seasonValue) {
      return;
    }

    setIsSubmitting(true);
    const formattedSeason = formatSeasonCode(seasonValue);
    const response = await api.createLibrarySeasons(seriesCode, [formattedSeason]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add season', description: response.error, status: 'error' });
      return;
    }

    setNewSeasonBySeries((prev) => ({ ...prev, [seriesCode]: '' }));
    toast({ title: 'Season added', status: 'success' });
    await refreshExplorer();
  };

  const handleAddEpisode = async (seriesCode: string, seasonCode: string) => {
    const key = `${seriesCode}-${seasonCode}`;
    const episodeValue = newEpisodeBySeason[key]?.trim();
    if (!episodeValue) {
      return;
    }

    setIsSubmitting(true);
    const formattedEpisode = formatEpisodeCode(episodeValue);
    const response = await api.createLibraryEpisodes(seriesCode, seasonCode, [formattedEpisode]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add episode', description: response.error, status: 'error' });
      return;
    }

    setNewEpisodeBySeason((prev) => ({ ...prev, [key]: '' }));
    await refreshExplorer();
  };

  const handleDeleteFile = async (fileType: 'plot' | 'srt') => {
    if (!selectedEpisode) return;
    
    setIsSubmitting(true);
    const response = await api.deleteEpisodeFile(selectedEpisode.series, selectedEpisode.season, selectedEpisode.episode, fileType);
    setIsSubmitting(false);

    if (isApiSuccess(response)) {
      toast({ title: 'File deleted', status: 'success' });
      await refreshExplorer();
      
      // Update local state
      const seriesData = response.data as unknown as ExplorerSeries;
      const updatedSeason = seriesData.seasons?.find(s => s.season === selectedEpisode.season);
      const updatedEpisode = updatedSeason?.episodes.find(e => (e as any).episode === selectedEpisode.episode);
      if (updatedEpisode) {
        setSelectedEpisode(updatedEpisode);
      }
      
      if (fileType === 'plot') {
        setPlotContent('');
      }
    } else {
      toast({ title: 'Delete failed', description: response.error, status: 'error' });
    }
  };

  const handleUpload = async (kind: 'plot' | 'srt', file: File) => {
    if (!selectedEpisode) {
      return;
    }

    const expectedExtension = kind === 'plot' ? '.txt' : '.srt';
    if (!file.name.toLowerCase().endsWith(expectedExtension)) {
      toast({ title: `Please upload a ${expectedExtension} file in the ${kind.toUpperCase()} box.`, status: 'warning' });
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsSubmitting(true);
    const response = await api.request<any>(
      `/library/series/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/upload`,
      {
        method: 'POST',
        body: formData,
      }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      const errorMsg = isApiError(response) ? response.error : 'Upload failed';
      toast({ title: 'Unable to upload file', description: errorMsg, status: 'error' });
      return;
    }

    toast({ title: 'Upload successful', status: 'success' });
    
    // Refresh the whole library to get the updated status
    const allSeries = await refreshExplorer();
    
    // Update selected episode from the newly fetched data
    if (allSeries) {
      const updatedSeries = allSeries.find(s => s.code === selectedEpisode.series);
      const updatedSeason = updatedSeries?.seasons?.find(s => s.season === selectedEpisode.season);
      const updatedEpisode = updatedSeason?.episodes.find(e => e.episode === selectedEpisode.episode);
      if (updatedEpisode) {
        setSelectedEpisode(updatedEpisode);
        if (kind === 'plot' || (kind === 'srt' && updatedEpisode.has_plot_file)) {
          void fetchPlotContent(updatedEpisode.series, updatedEpisode.season, updatedEpisode.episode);
        }
      }
    }
  };

  const handleGeneratePlot = async () => {
    if (!selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request<ExplorerEpisodeStatus>(
      `/library/explorer/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/generate-plot`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess<ExplorerEpisodeStatus>(response)) {
      toast({ title: 'Unable to generate plot', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Plot generated', status: 'success' });
    await refreshExplorer();
    setSelectedEpisode(response.data);
    void fetchPlotContent(response.data.series, response.data.season, response.data.episode);
  };


  const handleResetEpisode = async () => {
    if (!selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request<{ episode: ExplorerEpisodeStatus }>(
      `/library/explorer/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/reset`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess<{ episode: ExplorerEpisodeStatus }>(response)) {
      toast({ title: 'Unable to reset episode', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Episode reset completed', status: 'success' });
    await refreshExplorer();
    setSelectedEpisode(response.data.episode);
  };

  const handleResetSeason = async (seriesCode: string, seasonCode: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to reset ${seasonCode}? This will delete all analysis artifacts for this season, AND all character data for the entire series from the database.`
    );
    if (!confirmed) return;

    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesCode}/${seasonCode}/reset`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to reset season', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Season reset completed', status: 'success' });
    await refreshExplorer();
    if (selectedEpisode && selectedEpisode.series === seriesCode && selectedEpisode.season === seasonCode) {
      setSelectedEpisode(null); // Clear selected episode as it might have been reset
    }
  };

  const statusColor = (status: ExplorerEpisodeStatus['analysis_status']) => {
    if (status === 'completed') return 'green';
    if (status === 'error') return 'red';
    if (status === 'pending') return 'blue';
    if (status === 'missing_files') return 'orange';
    return 'gray';
  };

  const statusLabel = (status: ExplorerEpisodeStatus['analysis_status']) => {
    if (status === 'completed') return 'Analyzed';
    if (status === 'error') return 'Error';
    if (status === 'pending') return 'Ready';
    if (status === 'missing_files') return 'Missing Files';
    return 'Not Started';
  };

  return (
    <Box bg="white" p={6} borderRadius="lg" shadow="sm">
      {!selectedSeriesData ? (
        <VStack align="center" justify="center" minH="400px" spacing={4} color="gray.500">
          <Text fontSize="xl" fontWeight="bold">Library Explorer</Text>
          <Text>Select a series from the sidebar to manage its seasons and episodes.</Text>
        </VStack>
      ) : (
        <Box>
          {/* If no episode is selected, show the series overview (seasons and episodes grid) */}
          {!selectedEpisode ? (
            <VStack align="stretch" spacing={6}>
              <Box>
                <Text fontSize="2xl" fontWeight="bold" color="blue.600">{selectedSeriesData.display_name}</Text>
                <Text fontSize="md" color="gray.600">Manage seasons and episodes for this series.</Text>
              </Box>
              
              <Divider />
              
              <VStack align="stretch" spacing={6} width="100%">
                {selectedSeriesData.seasons?.map((seasonItem) => {
                  const seasonKey = `${selectedSeriesData.code}-${seasonItem.season}`;
                  return (
                    <Box key={seasonItem.season} p={5} borderWidth="1px" borderRadius="lg" bg="white" shadow="sm">
                      <HStack justify="space-between" mb={4}>
                        <Text fontSize="lg" fontWeight="bold">{seasonItem.season}</Text>
                        <Button 
                          size="xs" 
                          colorScheme="red" 
                          variant="ghost"
                          onClick={() => handleResetSeason(selectedSeriesData.code, seasonItem.season)}
                          isLoading={isSubmitting}
                        >
                          Reset Season
                        </Button>
                      </HStack>
                      
                      <SimpleGrid columns={5} spacing={3} mb={6}>
                        {seasonItem.episodes.map((episodeItem) => (
                          <Button
                            key={episodeItem.episode}
                            size="sm"
                            variant={selectedEpisode && (selectedEpisode as any).episode === episodeItem.episode ? 'solid' : 'outline'}
                            colorScheme={statusColor(episodeItem.analysis_status)}
                            onClick={() => setSelectedEpisode(episodeItem)}
                            _hover={{ transform: 'translateY(-2px)', shadow: 'md' }}
                            transition="all 0.2s"
                          >
                            {episodeItem.episode}
                          </Button>
                        ))}
                      </SimpleGrid>
                      
                      <HStack bg="gray.50" p={2} borderRadius="md">
                        <Input
                          size="sm"
                          placeholder="New episode number (e.g., 01)"
                          value={newEpisodeBySeason[seasonKey] ?? ''}
                          bg="white"
                          onChange={(event) => setNewEpisodeBySeason((prev) => ({ ...prev, [seasonKey]: event.target.value }))}
                        />
                        <Button size="sm" colorScheme="blue" onClick={() => handleAddEpisode(selectedSeriesData.code, seasonItem.season)} isLoading={isSubmitting}>
                          Add
                        </Button>
                      </HStack>
                    </Box>
                  );
                })}
                
                <Box p={5} border="2px dashed" borderColor="gray.300" borderRadius="lg" bg="gray.50">
                  <VStack spacing={3}>
                    <Text fontWeight="bold" color="gray.600">Add New Season</Text>
                    <HStack width="100%">
                      <Input
                        size="sm"
                        bg="white"
                        placeholder="Season code (e.g., S01)"
                        value={newSeasonBySeries[selectedSeriesData.code] ?? ''}
                        onChange={(event) => setNewSeasonBySeries((prev) => ({ ...prev, [selectedSeriesData.code]: event.target.value }))}
                      />
                      <Button size="sm" colorScheme="blue" onClick={() => handleAddSeason(selectedSeriesData.code)} isLoading={isSubmitting}>
                        Create Season
                      </Button>
                    </HStack>
                  </VStack>
                </Box>
              </VStack>
            </VStack>
          ) : (
            /* If an episode is selected, show the episode detail manager */
            <VStack align="stretch" spacing={4}>
              {isRefreshing ? <Text color="gray.500">Refreshing library status...</Text> : null}
              <HStack justify="space-between">
                <Box>
                  <HStack>
                    <Button size="sm" variant="ghost" onClick={() => setSelectedEpisode(null)}>← Back to Series</Button>
                    <Text fontSize="lg" fontWeight="bold">{selectedEpisode.series} {selectedEpisode.season}{selectedEpisode.episode}</Text>
                  </HStack>
                  <Text color="gray.600" ml={10}>Episode processing status from filesystem and database.</Text>
                </Box>
                <Badge colorScheme={statusColor(selectedEpisode.analysis_status)}>{statusLabel(selectedEpisode.analysis_status)}</Badge>
              </HStack>

              <Divider />

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                <Box borderWidth="1px" borderRadius="md" p={4}>
                  <HStack justify="space-between" mb={1}>
                    <Text fontWeight="medium">Plot file</Text>
                    {selectedEpisode.has_plot_file && (
                      <IconButton
                        aria-label="Delete plot"
                        icon={<DeleteIcon />}
                        size="xs"
                        variant="ghost"
                        colorScheme="red"
                        onClick={() => handleDeleteFile('plot')}
                        isLoading={isSubmitting}
                      />
                    )}
                  </HStack>
                  <Text color={selectedEpisode.has_plot_file ? 'green.600' : 'gray.500'}>
                    {selectedEpisode.has_plot_file ? 'Present' : 'Missing'}
                  </Text>
                  <Box
                    mt={3}
                    border="2px dashed"
                    borderColor="gray.200"
                    borderRadius="md"
                    p={4}
                    textAlign="center"
                    bg="gray.50"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={async (event) => {
                      event.preventDefault();
                      const file = event.dataTransfer.files[0];
                      if (file) {
                        await handleUpload('plot', file);
                      }
                    }}
                  >
                    <Text fontSize="sm" mb={2}>Drop plot .txt here</Text>
                    <Input
                      type="file"
                      accept=".txt"
                      onChange={async (event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                          await handleUpload('plot', file);
                        }
                        event.target.value = '';
                      }}
                    />
                  </Box>
                </Box>
                <Box borderWidth="1px" borderRadius="md" p={4}>
                  <HStack justify="space-between" mb={1}>
                    <Text fontWeight="medium">SRT subtitles</Text>
                    {selectedEpisode.has_srt_file && (
                      <IconButton
                        aria-label="Delete SRT"
                        icon={<DeleteIcon />}
                        size="xs"
                        variant="ghost"
                        colorScheme="red"
                        onClick={() => handleDeleteFile('srt')}
                        isLoading={isSubmitting}
                      />
                    )}
                  </HStack>
                  <Text color={selectedEpisode.has_srt_file ? 'green.600' : 'gray.500'}>
                    {selectedEpisode.has_srt_file ? 'Present' : 'Missing'}
                  </Text>
                  <Box
                    mt={3}
                    border="2px dashed"
                    borderColor="gray.200"
                    borderRadius="md"
                    p={4}
                    textAlign="center"
                    bg="gray.50"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={async (event) => {
                      event.preventDefault();
                      const file = event.dataTransfer.files[0];
                      if (file) {
                        await handleUpload('srt', file);
                      }
                    }}
                  >
                    <Text fontSize="sm" mb={2}>Drop subtitle .srt here</Text>
                    <Input
                      type="file"
                      accept=".srt"
                      onChange={async (event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                          await handleUpload('srt', file);
                        }
                        event.target.value = '';
                      }}
                    />
                  </Box>
                </Box>
              </SimpleGrid>

              {selectedEpisode.has_plot_file && (
                <Box p={4} borderWidth="1px" borderRadius="md" bg="blue.50">
                  <Text fontWeight="bold" mb={2} color="blue.700">Detailed Plot Preview</Text>
                  {isFetchingPlot ? (
                    <HStack py={4} justify="center">
                      <Spinner size="sm" />
                      <Text ml={2}>Loading plot content...</Text>
                    </HStack>
                  ) : (
                    <Textarea
                      value={plotContent}
                      readOnly
                      rows={8}
                      bg="white"
                      fontSize="sm"
                      placeholder="Plot content will appear here..."
                    />
                  )}
                </Box>
              )}

              <Box>
                <Text fontWeight="medium" mb={2}>Actions</Text>
                <HStack spacing={3}>
                  <Button
                    onClick={handleGeneratePlot}
                    isLoading={isSubmitting}
                    isDisabled={!selectedEpisode.has_srt_file || selectedEpisode.has_plot_file}
                  >
                    Generate detailed plot from SRT
                  </Button>
                  <Button
                    onClick={handleResetEpisode}
                    isLoading={isSubmitting}
                    isDisabled={!selectedEpisode.has_plot_file && !selectedEpisode.has_analysis_artifacts && selectedEpisode.progression_count === 0}
                  >
                    Reset episode analysis
                  </Button>
                </HStack>
              </Box>
            </VStack>
          )}
        </Box>
      )}
    </Box>
  );
};
