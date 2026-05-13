import React, { useState, useEffect, useMemo } from 'react';
import { Badge, Box, Button, HStack, Select, SimpleGrid, Text, VStack, useToast, IconButton } from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';

import type { ExplorerSeries } from '@/architecture/types';
import { isApiError } from '@/architecture/types/api';

interface AnalysisEnginePanelProps {
  seriesList: ExplorerSeries[];
  selectedSeriesCode: string;
  onSelectSeries: (series: string) => void;
  onSelectSeriesManager?: () => void;
  onRefresh?: () => Promise<void>;
}

const api = new ApiClient();

export const AnalysisEnginePanel: React.FC<AnalysisEnginePanelProps> = ({
  seriesList,
  selectedSeriesCode,
  onSelectSeries: _, // Mark as unused
  onSelectSeriesManager,
  onRefresh,
}) => {
  const toast = useToast();
  const [selectedSeason, setSelectedSeason] = useState('');
  const [selectedEpisode, setSelectedEpisode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const seriesData = useMemo(
    () => seriesList.find((series) => series.code === selectedSeriesCode) ?? null,
    [seriesList, selectedSeriesCode]
  );
  const seasons = useMemo(() => seriesData?.seasons ?? [], [seriesData]);
  const episodesForSeason = useMemo(
    () => seasons.find((season) => season.season === selectedSeason)?.episodes ?? [],
    [seasons, selectedSeason]
  );

  if (!seriesData) {
    return (
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text color="gray.600">Select a series from the catalogue to access the Analysis Engine.</Text>
      </Box>
    );
  }

  const seasonCount = seriesData.seasons?.length ?? 0;
  const episodeCount = seriesData.seasons?.reduce((total, season) => total + season.episodes.length, 0) ?? 0;
  const plotReadyCount = seriesData.seasons?.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'pending').length,
    0
  ) ?? 0;
  const subtitleOnlyCount = seriesData.seasons?.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'not_processed').length,
    0
  ) ?? 0;
  const processedCount = seriesData.seasons?.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'completed').length,
    0
  ) ?? 0;
  const errorCount = seriesData.seasons?.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'error').length,
    0
  ) ?? 0;

  const handleNarrativeArcExtraction = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesData.code}/${selectedSeason}/${selectedEpisode}/narrative-arc-extraction`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      const errorMsg = isApiError(response) ? response.error : 'Arc extraction failed';
      toast({ title: 'Unable to extract arcs', description: errorMsg, status: 'error' });
      return;
    }

    toast({ title: 'Narrative arc extraction completed', status: 'success' });
    await onRefresh?.();
  };

  const handleAnalyzeSeason = async () => {
    if (!seriesData || !selectedSeason) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesData.code}/${selectedSeason}/analyze-ready`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      const errorMsg = isApiError(response) ? response.error : 'Analysis failed';
      toast({ title: 'Unable to analyze season', description: errorMsg, status: 'error' });
      return;
    }

    toast({ title: 'Season analysis completed', status: 'success' });
    await onRefresh?.();
  };

  const handleAnalyzeSeries = async () => {
    if (!seriesData) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.analyzeLibrarySeries(seriesData.code);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      const errorMsg = isApiError(response) ? response.error : 'Analysis failed';
      toast({ title: 'Unable to analyze series', description: errorMsg, status: 'error' });
      return;
    }

    toast({ title: 'Series analysis started', status: 'success' });
    await onRefresh?.();
  };

  const handleGeneratePlotFromVideo = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) return;
    setIsSubmitting(true);
    const response = await api.fullVideoToPlot(seriesData.code, selectedSeason, selectedEpisode);
    setIsSubmitting(false);
    if (isApiSuccess(response)) {
      toast({ title: 'Plot generated from video', status: 'success' });
      await onRefresh?.();
    } else {
      toast({ title: 'Generation failed', description: response.error, status: 'error' });
    }
  };

  const handleGeneratePlotFromSrt = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) return;
    setIsSubmitting(true);
    const response = await api.generatePlotFromSrt(seriesData.code, selectedSeason, selectedEpisode);
    setIsSubmitting(false);
    if (isApiSuccess(response)) {
      toast({ title: 'Plot generated from SRT', status: 'success' });
      await onRefresh?.();
    } else {
      toast({ title: 'Generation failed', description: response.error, status: 'error' });
    }
  };

  const handleExtractNarrativeArcs = async () => {
    await handleNarrativeArcExtraction();
  };

  const handleSemanticSceneSplitting = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) return;
    setIsSubmitting(true);
    const response = await api.analyzeVideoScenes(seriesData.code, selectedSeason, selectedEpisode);
    setIsSubmitting(false);
    if (isApiSuccess(response)) {
      toast({ title: 'Video scenes extracted', status: 'success' });
      await onRefresh?.();
    } else {
      toast({ title: 'Extraction failed', description: response.error, status: 'error' });
    }
  };

  const handleResetNarrative = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) return;
    if (!window.confirm("Are you sure you want to reset narrative arcs? This will delete all arcs, characters, and progressions for this episode from DB and Vector Store.")) return;
    
    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesData.code}/${selectedSeason}/${selectedEpisode}/reset-narrative`,
      { method: 'POST' }
    );
    setIsSubmitting(false);
    
    if (isApiSuccess(response)) {
      toast({ title: 'Narrative reset successful', status: 'success' });
      await onRefresh?.();
    } else {
      const errorMsg = isApiError(response) ? response.error : 'Reset failed';
      toast({ title: 'Reset failed', description: errorMsg, status: 'error' });
    }
  };

  const handleResetVideo = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) return;
    if (!window.confirm("Are you sure you want to delete all extracted video clips for this episode?")) return;

    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesData.code}/${selectedSeason}/${selectedEpisode}/reset-video`,
      { method: 'POST' }
    );
    setIsSubmitting(false);
    
    if (isApiSuccess(response)) {
      toast({ title: 'Video clips reset successful', status: 'success' });
      await onRefresh?.();
    } else {
      const errorMsg = isApiError(response) ? response.error : 'Reset failed';
      toast({ title: 'Reset failed', description: errorMsg, status: 'error' });
    }
  };

  const currentEpisodeData = useMemo(() => {
    return episodesForSeason.find(e => e.episode === selectedEpisode);
  }, [episodesForSeason, selectedEpisode]);

  return (
    <VStack align="stretch" spacing={6}>
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <HStack justify="space-between" align="center">
          <VStack align="left" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold" color="blue.600">{seriesData.display_name}</Text>
            <Text fontSize="sm" color="gray.500" fontWeight="medium">Analysis Engine Dashboard | {seriesData.code}</Text>
          </VStack>
          <Badge colorScheme="blue" variant="subtle" px={3} py={1} borderRadius="full">
            Series Selected
          </Badge>
        </HStack>
      </Box>

      {/* Series Summary */}
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <HStack justify="space-between" mb={4}>
          <Text fontWeight="bold">Series Readiness Summary</Text>
          <HStack>
            <Button size="sm" onClick={handleAnalyzeSeries} isLoading={isSubmitting}>Analyze Whole Series</Button>
            <Button size="sm" onClick={onSelectSeriesManager}>Series Manager</Button>
          </HStack>
        </HStack>
        <SimpleGrid columns={[2, 3, 4]} spacing={4}>
          <Box p={3} border="1px solid" borderColor="gray.100" borderRadius="md">
            <Text fontSize="xs" color="gray.500">Seasons</Text>
            <Text fontWeight="bold">{seasonCount}</Text>
          </Box>
          <Box p={3} border="1px solid" borderColor="gray.100" borderRadius="md">
            <Text fontSize="xs" color="gray.500">Episodes</Text>
            <Text fontWeight="bold">{episodeCount}</Text>
          </Box>
          <Box p={3} border="1px solid" borderColor="gray.100" borderRadius="md">
            <Text fontSize="xs" color="gray.500">Completed</Text>
            <Text fontWeight="bold" color="green.500">{processedCount}</Text>
          </Box>
          <Box p={3} border="1px solid" borderColor="gray.100" borderRadius="md">
            <Text fontSize="xs" color="gray.500">Errors</Text>
            <Text fontWeight="bold" color="red.500">{errorCount}</Text>
          </Box>
        </SimpleGrid>
      </Box>

      {/* Analysis Selection */}
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text fontWeight="bold" mb={4}>Target Selection</Text>
        <HStack spacing={4}>
          <Select placeholder="Select season" value={selectedSeason} onChange={(event) => setSelectedSeason(event.target.value)}>
            {seasons.map((season) => (
              <option key={season.season} value={season.season}>{season.season}</option>
            ))}
          </Select>
          <Select placeholder="Select episode" value={selectedEpisode} onChange={(event) => setSelectedEpisode(event.target.value)}>
            {episodesForSeason.map((episode) => (
              <option key={episode.episode} value={episode.episode}>{episode.episode} - {episode.analysis_status}</option>
            ))}
          </Select>
          <Button colorScheme="blue" variant="outline" onClick={handleAnalyzeSeason} isLoading={isSubmitting} isDisabled={!selectedSeason}>
            Batch Season
          </Button>
        </HStack>
      </Box>

      {/* Analysis Dashboard */}
      {selectedEpisode && currentEpisodeData && (
        <SimpleGrid columns={[1, 1, 2]} spacing={6}>
          {/* Card 1: Ingestion */}
          <Box bg="white" p={6} borderRadius="lg" shadow="md" borderTop="4px solid" borderColor="teal.500">
            <VStack align="stretch" spacing={4}>
              <HStack justify="space-between">
                <VStack align="left" spacing={1}>
                  <Text fontWeight="bold" fontSize="lg">Generate Dialogues and Plot from Video</Text>
                  {(currentEpisodeData.has_plot_file || currentEpisodeData.has_srt_file) && (
                    <Badge colorScheme="orange" variant="subtle" fontSize="xs">ALREADY COMPLETED</Badge>
                  )}
                </VStack>
                <Badge colorScheme={currentEpisodeData.has_video_file ? 'green' : 'gray'}>
                  {currentEpisodeData.has_video_file ? 'Video Present' : 'Video Missing'}
                </Badge>
              </HStack>
              <Text fontSize="sm" color="gray.600">
                {currentEpisodeData.has_plot_file || currentEpisodeData.has_srt_file 
                  ? "Notice: Dialogue or Plot already exists. Running this will overwrite them."
                  : "Automatically transcribe the video and generate an initial plot summary."}
              </Text>
              <Button 
                colorScheme="teal" 
                onClick={handleGeneratePlotFromVideo} 
                isLoading={isSubmitting}
                isDisabled={!currentEpisodeData.has_video_file}
              >
                Run Ingestion
              </Button>
            </VStack>
          </Box>

          {/* Card 2: Plot from Dialogues */}
          <Box bg="white" p={6} borderRadius="lg" shadow="md" borderTop="4px solid" borderColor="orange.500">
            <VStack align="stretch" spacing={4}>
              <HStack justify="space-between">
                <VStack align="left" spacing={1}>
                  <Text fontWeight="bold" fontSize="lg">Generate Plot from Dialogues</Text>
                  {currentEpisodeData.has_plot_file && (
                    <Badge colorScheme="orange" variant="subtle" fontSize="xs">ALREADY COMPLETED</Badge>
                  )}
                </VStack>
                <Badge colorScheme={currentEpisodeData.has_srt_file ? 'green' : 'gray'}>
                  {currentEpisodeData.has_srt_file ? 'SRT Present' : 'SRT Missing'}
                </Badge>
              </HStack>
              <Text fontSize="sm" color="gray.600">
                {currentEpisodeData.has_plot_file 
                  ? "Notice: Plot already exists. Running this will overwrite it."
                  : "Generate or refine the narrative plot based on existing subtitle dialogues."}
              </Text>
              <Button 
                colorScheme="orange" 
                onClick={handleGeneratePlotFromSrt} 
                isLoading={isSubmitting}
                isDisabled={!currentEpisodeData.has_srt_file}
              >
                Run Plot Generation
              </Button>
            </VStack>
          </Box>

          {/* Card 3: Arc Extraction */}
          <Box bg="white" p={6} borderRadius="lg" shadow="md" borderTop="4px solid" borderColor="blue.500">
            <VStack align="stretch" spacing={4}>
              <HStack justify="space-between">
                <VStack align="left" spacing={1}>
                  <HStack spacing={2}>
                    <Text fontWeight="bold" fontSize="lg">Narrative Arc Extraction</Text>
                    {currentEpisodeData.analysis_status === 'completed' && (
                      <>
                        <Badge colorScheme="orange" variant="subtle" fontSize="xs">ALREADY COMPLETED</Badge>
                        <IconButton
                          aria-label="Reset narrative arcs"
                          icon={<DeleteIcon />}
                          size="xs"
                          colorScheme="red"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); handleResetNarrative(); }}
                        />
                      </>
                    )}
                  </HStack>
                </VStack>
                <Badge colorScheme={currentEpisodeData.has_plot_file ? 'green' : 'gray'}>
                  {currentEpisodeData.has_plot_file ? 'Plot Ready' : 'Plot Missing'}
                </Badge>
              </HStack>
              <Text fontSize="sm" color="gray.600">
                {currentEpisodeData.analysis_status === 'completed'
                  ? "Notice: Narrative arcs have already been extracted. Running this will re-analyze the episode."
                  : "Extract characters, entities, and narrative arcs using the multi-agent AI framework."}
              </Text>
              <Button 
                colorScheme="blue" 
                onClick={handleExtractNarrativeArcs} 
                isLoading={isSubmitting}
                isDisabled={!currentEpisodeData.has_plot_file}
              >
                Run Narrative Analysis
              </Button>
            </VStack>
          </Box>

          {/* Card 4: Scene Splitting */}
          <Box bg="white" p={6} borderRadius="lg" shadow="md" borderTop="4px solid" borderColor="purple.500">
            <VStack align="stretch" spacing={4}>
              <HStack justify="space-between">
                <VStack align="left" spacing={1}>
                  <HStack spacing={2}>
                    <Text fontWeight="bold" fontSize="lg">Semantic Video Scene Splitting</Text>
                    {currentEpisodeData.has_clips && (
                      <>
                        <Badge colorScheme="orange" variant="subtle" fontSize="xs">ALREADY COMPLETED</Badge>
                        <IconButton
                          aria-label="Reset video clips"
                          icon={<DeleteIcon />}
                          size="xs"
                          colorScheme="red"
                          variant="ghost"
                          onClick={(e) => { e.stopPropagation(); handleResetVideo(); }}
                        />
                      </>
                    )}
                  </HStack>
                </VStack>
                <Badge colorScheme={currentEpisodeData.has_video_file && currentEpisodeData.has_plot_file && currentEpisodeData.has_srt_file ? 'green' : 'gray'}>
                  {currentEpisodeData.has_video_file && currentEpisodeData.has_plot_file && currentEpisodeData.has_srt_file ? 'Ready' : 'Missing Assets'}
                </Badge>
              </HStack>
              <Text fontSize="sm" color="gray.600">
                {currentEpisodeData.has_clips 
                  ? "Notice: Clips already exist. Running this will empty the clips folder and re-extract them."
                  : "Subdivide the episode into individual video clips based on semantic plot segments."}
              </Text>
              <Button 
                colorScheme="purple" 
                onClick={handleSemanticSceneSplitting} 
                isLoading={isSubmitting}
                isDisabled={!currentEpisodeData.has_video_file || !currentEpisodeData.has_plot_file || !currentEpisodeData.has_srt_file}
              >
                Run Scene Splitting
              </Button>
            </VStack>
          </Box>
        </SimpleGrid>
      )}
    </VStack>
  );
};
