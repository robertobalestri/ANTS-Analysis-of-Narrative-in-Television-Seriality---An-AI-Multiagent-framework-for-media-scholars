import React, { useState, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Select,
  FormControl,
  FormLabel,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  Badge
} from '@chakra-ui/react';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import type { ExplorerSeries } from '@/architecture/types';

interface EpisodeAnalyzerProps {
  seriesList: ExplorerSeries[];
  selectedSeriesCode: string;
  onAnalyze: (srtContent: string, episodeRef: string, videoPath?: string) => Promise<void>;
  isAnalyzing: boolean;
}

const api = ApiClient.getInstance();

export const EpisodeAnalyzer: React.FC<EpisodeAnalyzerProps> = ({
  seriesList,
  selectedSeriesCode,
  onAnalyze,
  isAnalyzing
}) => {
  const toast = useToast();
  const [selectedSeason, setSelectedSeason] = useState('');
  const [selectedEpisode, setSelectedEpisode] = useState('');
  const [analyzingEpisode, setAnalyzingEpisode] = useState('');
  const [loading, setLoading] = useState(false);

  const seriesData = useMemo(
    () => seriesList.find((s) => s.code === selectedSeriesCode) ?? null,
    [seriesList, selectedSeriesCode]
  );
  const seasons = useMemo(
    () => seriesData?.seasons ?? [],
    [seriesData]
  );

  // Only include seasons that have episodes with SRT files
  const seasonsWithSrt = useMemo(() => {
    return seasons.filter(season =>
      season.episodes.some(ep => ep.has_srt_file)
    );
  }, [seasons]);

  const episodesForSeason = useMemo(
    () => seasons.find((s) => s.season === selectedSeason)?.episodes ?? [],
    [seasons, selectedSeason]
  );

  // Only include episodes that have SRT files
  const srtEpisodes = useMemo(
    () => episodesForSeason.filter(ep => ep.has_srt_file),
    [episodesForSeason]
  );

  const selectedEpisodeData = useMemo(() => {
    if (!selectedSeason || !selectedEpisode) return null;
    return episodesForSeason.find(
      ep => ep.episode === selectedEpisode
    );
  }, [episodesForSeason, selectedSeason, selectedEpisode]);

  const handleAnalyze = async () => {
    if (!selectedEpisodeData || !seriesData || !selectedSeason) return;

    setAnalyzingEpisode(selectedEpisode);
    setLoading(true);
    try {
      const srtResponse = await api.getEpisodeFile(
        seriesData.code,
        selectedSeason,
        selectedEpisode,
        'srt'
      );

      if (!isApiSuccess(srtResponse) || !srtResponse.data?.content) {
        toast({ title: 'Failed to read SRT file', status: 'error' });
        return;
      }

      const videoPath = selectedEpisodeData.has_video_file && selectedEpisodeData.video_filename
        ? `data/${seriesData.code}/${selectedSeason}/${selectedEpisode}/${selectedEpisodeData.video_filename}`
        : undefined;

      const episodeRef = `${selectedSeason}${selectedEpisode}`;
      await onAnalyze(srtResponse.data.content, episodeRef, videoPath);

    } catch {
      toast({ title: 'Analysis failed', status: 'error' });
    } finally {
      setLoading(false);
      setAnalyzingEpisode('');
    }
  };

  if (!seriesData) {
    return (
      <Box p={4} textAlign="center">
        <Text color="gray.500">Select a series to analyze episodes</Text>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box p={4} textAlign="center">
        <Spinner />
        <Text mt={2} fontSize="sm" color="gray.500">Loading...</Text>
      </Box>
    );
  }

  if (seasonsWithSrt.length === 0) {
    return (
      <Box p={4}>
        <Alert status="warning">
          <AlertIcon />
          <Box>
            <Text fontWeight="medium">No episodes with SRT files</Text>
            <Text fontSize="sm">Upload SRT files in Series Manager first.</Text>
          </Box>
        </Alert>
      </Box>
    );
  }

  return (
    <VStack align="stretch" spacing={4}>
      <FormControl>
        <FormLabel fontSize="sm">Season</FormLabel>
        <Select
          value={selectedSeason}
          onChange={(e) => {
            setSelectedSeason(e.target.value);
            setSelectedEpisode('');
          }}
          placeholder="Select season"
        >
          {seasonsWithSrt.map(season => (
            <option key={season.season} value={season.season}>{season.season}</option>
          ))}
        </Select>
      </FormControl>

      <FormControl>
        <FormLabel fontSize="sm">Episode</FormLabel>
        <Select
          value={selectedEpisode}
          onChange={(e) => setSelectedEpisode(e.target.value)}
          placeholder="Select episode"
          isDisabled={!selectedSeason}
        >
          {srtEpisodes.map(ep => (
            <option key={ep.episode} value={ep.episode}>
              {ep.episode} {ep.has_video_file ? '📹' : ''}
            </option>
          ))}
        </Select>
      </FormControl>

      {selectedEpisodeData && (
        <Box p={3} borderWidth="1px" borderRadius="md" bg="gray.50">
          <HStack justify="space-between" mb={2}>
            <Text fontWeight="bold">{selectedSeason}{selectedEpisodeData.episode}</Text>
            <HStack>
              <Badge colorScheme={selectedEpisodeData.has_srt_file ? 'green' : 'red'}>SRT</Badge>
              <Badge colorScheme={selectedEpisodeData.has_video_file ? 'blue' : 'gray'}>Video</Badge>
              <Badge colorScheme={selectedEpisodeData.has_plot_file ? 'purple' : 'gray'}>Plot</Badge>
            </HStack>
          </HStack>
          <Text fontSize="xs" color="gray.600">
            {selectedEpisodeData.has_srt_file ? '✓ SRT file ready' : '✗ No SRT file'} •{' '}
            {selectedEpisodeData.has_video_file ? '✓ Video ready' : '✗ No video'} •{' '}
            {selectedEpisodeData.has_plot_file ? '✓ Plot ready' : '✗ No plot'}
          </Text>
        </Box>
      )}

      <Button
        colorScheme="blue"
        onClick={handleAnalyze}
        isLoading={isAnalyzing || analyzingEpisode !== ''}
        loadingText={`Analyzing ${analyzingEpisode || '...'}...`}
        isDisabled={!selectedEpisode}
      >
        Analyze Episode
      </Button>
    </VStack>
  );
};