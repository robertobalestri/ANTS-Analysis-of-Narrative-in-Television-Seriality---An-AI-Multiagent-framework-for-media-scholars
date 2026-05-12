import React, { useMemo, useState } from 'react';
import { Badge, Box, Button, HStack, Select, Text, VStack, useToast } from '@chakra-ui/react';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';

interface ExplorerEpisodeStatus {
  series: string;
  season: string;
  episode: string;
  has_plot_file: boolean;
  has_srt_file: boolean;
  has_dialogue_json: boolean;
  has_analysis_artifacts: boolean;
  progression_count: number;
  analysis_status: 'completed' | 'error' | 'pending' | 'not_processed';
}

interface ExplorerSeason {
  season: string;
  episodes: ExplorerEpisodeStatus[];
}

interface ExplorerSeries {
  code: string;
  display_name: string;
  seasons: ExplorerSeason[];
}

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
  onSelectSeries,
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

  const seasonCount = seriesData.seasons.length;
  const episodeCount = seriesData.seasons.reduce((total, season) => total + season.episodes.length, 0);
  const plotReadyCount = seriesData.seasons.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'pending').length,
    0
  );
  const subtitleOnlyCount = seriesData.seasons.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'not_processed').length,
    0
  );
  const processedCount = seriesData.seasons.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'completed').length,
    0
  );
  const errorCount = seriesData.seasons.reduce(
    (total, season) => total + season.episodes.filter((episode) => episode.analysis_status === 'error').length,
    0
  );

  const handleAnalyzeEpisode = async () => {
    if (!seriesData || !selectedSeason || !selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request(
      `/library/explorer/${seriesData.code}/${selectedSeason}/${selectedEpisode}/analyze`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to analyze episode', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Episode analysis completed', status: 'success' });
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
      toast({ title: 'Unable to analyze season', description: response.error, status: 'error' });
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
      toast({ title: 'Unable to analyze series', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Series analysis started', status: 'success' });
    await onRefresh?.();
  };

  return (
    <VStack align="stretch" spacing={6}>
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <HStack justify="space-between" align="center">
          <VStack align="left" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold" color="blue.600">{seriesData.display_name}</Text>
            <Text fontSize="sm" color="gray.500" fontWeight="medium">Analysis Engine | {seriesData.code}</Text>
          </VStack>
          <Badge colorScheme="blue" variant="subtle" px={3} py={1} borderRadius="full">
            Series Selected
          </Badge>
        </HStack>
      </Box>

      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text fontWeight="bold" mb={4}>Series readiness summary</Text>
        <VStack align="stretch" spacing={2}>
          <Text>Seasons: {seasonCount}</Text>
          <Text>Episodes: {episodeCount}</Text>
          <Text>Not processed episodes: {plotReadyCount}</Text>
          <Text>Pending episodes: {subtitleOnlyCount}</Text>
          <Text>Completed episodes: {processedCount}</Text>
          <Text>Error episodes: {errorCount}</Text>
        </VStack>
      </Box>

      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text fontWeight="bold" mb={4}>Run analysis</Text>
        <VStack align="stretch" spacing={4}>
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
          <HStack wrap="wrap">
            <Button onClick={handleAnalyzeEpisode} isLoading={isSubmitting} isDisabled={!selectedEpisode}>Analyze single episode</Button>
            <Button onClick={handleAnalyzeSeason} isLoading={isSubmitting} isDisabled={!selectedSeason}>Analyze single season</Button>
            <Button onClick={handleAnalyzeSeries} isLoading={isSubmitting}>Analyze whole series</Button>
          </HStack>
          <HStack>
            <Button onClick={onSelectSeriesManager}>Open Series Manager</Button>
          </HStack>
        </VStack>
      </Box>
    </VStack>
  );
};
