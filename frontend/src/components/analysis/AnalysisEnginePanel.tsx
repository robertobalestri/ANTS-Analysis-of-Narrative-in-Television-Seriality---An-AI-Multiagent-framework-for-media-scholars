import React, { useState, useMemo } from 'react';
import { Box, Button, HStack, Text, VStack, useToast, Table, Thead, Tbody, Tr, Th, Td, Checkbox, Icon, Tooltip } from '@chakra-ui/react';
import { CheckCircleIcon, WarningIcon, CloseIcon, TimeIcon } from '@chakra-ui/icons';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import type { ExplorerSeries } from '@/architecture/types';

interface AnalysisEnginePanelProps {
  seriesList: ExplorerSeries[];
  selectedSeriesCode: string;
  onSelectSeries: (series: string) => void;
  onSelectSeriesManager?: () => void;
  onRefresh?: () => Promise<void>;
}

const api = ApiClient.getInstance();

export const AnalysisEnginePanel: React.FC<AnalysisEnginePanelProps> = ({
  seriesList,
  selectedSeriesCode,
  onSelectSeriesManager,
  onRefresh,
}) => {
  const toast = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedEpisodeIds, setSelectedEpisodeIds] = useState<Set<string>>(new Set());

  const seriesData = useMemo(
    () => seriesList.find((series) => series.code === selectedSeriesCode) ?? null,
    [seriesList, selectedSeriesCode]
  );
  
  // Flatten episodes to simplify table rendering and sequential logic
  const flatEpisodes = useMemo(() => {
    if (!seriesData?.seasons) return [];
    return seriesData.seasons.flatMap(s => s.episodes).sort((a, b) => {
      if (a.season !== b.season) return a.season.localeCompare(b.season);
      return a.episode.localeCompare(b.episode);
    });
  }, [seriesData]);

  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedEpisodeIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedEpisodeIds(newSet);
  };

  const toggleAll = () => {
    if (selectedEpisodeIds.size === flatEpisodes.length) {
      setSelectedEpisodeIds(new Set());
    } else {
      setSelectedEpisodeIds(new Set(flatEpisodes.map(e => `${e.season}-${e.episode}`)));
    }
  };

  if (!seriesData) {
    return (
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text color="gray.600">Select a series from the catalogue to access the Analysis Engine.</Text>
      </Box>
    );
  }

  const selectedEpisodesList = flatEpisodes.filter(e => selectedEpisodeIds.has(`${e.season}-${e.episode}`));

  // Validates if the selected items for deletion obey the sequential constraint
  const validateSequentialDeletion = (statusKey: 'narrative_arc_extraction_status' | 'event_driven_video_analysis_status') => {
    // If I am deleting i, all j > i that are 'completed' MUST also be selected for deletion.
    let earliestSelectedIndex = -1;
    for (let i = 0; i < flatEpisodes.length; i++) {
      if (selectedEpisodeIds.has(`${flatEpisodes[i].season}-${flatEpisodes[i].episode}`)) {
        earliestSelectedIndex = i;
        break;
      }
    }

    if (earliestSelectedIndex === -1) return true; // nothing selected

    for (let i = earliestSelectedIndex; i < flatEpisodes.length; i++) {
      const ep = flatEpisodes[i];
      const isSelected = selectedEpisodeIds.has(`${ep.season}-${ep.episode}`);
      const isCompleted = ep[statusKey] === 'completed';
      
      if (isCompleted && !isSelected) {
        toast({
          title: 'Sequential Constraint Violated',
          description: `You cannot delete analysis for earlier episodes if subsequent episodes (like ${ep.season}E${ep.episode}) have completed analysis. Please select them as well.`,
          status: 'warning',
          duration: 6000,
        });
        return false;
      }
    }
    return true;
  };

  const handleGenerateMissingFiles = async () => {
    if (selectedEpisodesList.length === 0) return;
    setIsSubmitting(true);
    for (const ep of selectedEpisodesList) {
      toast({ title: `Processing ${ep.season}E${ep.episode}`, status: 'info', duration: 2000 });
      if (!ep.has_plot_file && ep.has_srt_file) {
        // SRT present, no plot -> Generate plot from SRT
        const res = await api.generatePlotFromSrt(seriesData.code, ep.season, ep.episode);
        if (!isApiSuccess(res)) {
          toast({ title: `Failed for ${ep.season}E${ep.episode}`, description: res.error, status: 'error' });
        }
      } else if (!ep.has_plot_file && !ep.has_srt_file && ep.has_video_file) {
        // Video present, no SRT, no plot -> Full pipeline (Transcribe -> Plot)
        const res = await api.fullVideoToPlot(seriesData.code, ep.season, ep.episode);
        if (!isApiSuccess(res)) {
          toast({ title: `Failed for ${ep.season}E${ep.episode}`, description: res.error, status: 'error' });
        }
      } else if (ep.has_plot_file && !ep.has_srt_file && ep.has_video_file) {
        // Plot & Video present, no SRT -> Transcribe video to generate SRT
        const res = await api.transcribeVideo(seriesData.code, ep.season, ep.episode);
        if (!isApiSuccess(res)) {
          toast({ title: `Failed for ${ep.season}E${ep.episode}`, description: res.error, status: 'error' });
        }
      } else if (ep.has_plot_file && !ep.has_srt_file && !ep.has_video_file) {
        // Only plot available
        toast({
          title: `Cannot generate for ${ep.season}E${ep.episode}`,
          description: "Only plot available, can't generate anything from this one.",
          status: 'warning',
        });
      } else if (!ep.has_plot_file && !ep.has_srt_file && !ep.has_video_file) {
        // Nothing available
        toast({
          title: `Cannot generate for ${ep.season}E${ep.episode}`,
          description: "No files available (Video, SRT, or Plot) to base generation on.",
          status: 'warning',
        });
      }
    }
    setIsSubmitting(false);
    toast({ title: 'Batch generation completed', status: 'success' });
    await onRefresh?.();
  };

  const handleBatchNarrativeExtraction = async () => {
    if (selectedEpisodesList.length === 0) return;
    setIsSubmitting(true);
    for (const ep of selectedEpisodesList) {
      if (ep.narrative_arc_extraction_status === 'completed') continue;
      if (!ep.has_plot_file) {
         toast({ title: `Skipping ${ep.season}E${ep.episode}`, description: 'Missing plot file', status: 'warning' });
         continue;
      }
      toast({ title: `Extracting arcs for ${ep.season}E${ep.episode}`, status: 'info', duration: 2000 });
      await api.request(
        `/library/explorer/${seriesData.code}/${ep.season}/${ep.episode}/narrative-arc-extraction`,
        { method: 'POST' }
      );
    }
    setIsSubmitting(false);
    toast({ title: 'Batch Narrative Arc Extraction completed', status: 'success' });
    await onRefresh?.();
  };

  const handleBatchEventDrivenAnalysis = async () => {
    if (selectedEpisodesList.length === 0) return;
    setIsSubmitting(true);
    for (const ep of selectedEpisodesList) {
      if (ep.event_driven_video_analysis_status === 'completed') continue;
      if (!ep.has_srt_file || (!ep.has_plot_file && ep.narrative_arc_extraction_status !== 'completed')) {
         toast({ title: `Skipping ${ep.season}E${ep.episode}`, description: 'Missing required assets', status: 'warning' });
         continue;
      }
      
      if (ep.narrative_arc_extraction_status !== 'completed') {
        toast({ title: `Pre-requisite: Arcs for ${ep.season}E${ep.episode}`, status: 'info', duration: 2000 });
        const arcRes = await api.request(
          `/library/explorer/${seriesData.code}/${ep.season}/${ep.episode}/narrative-arc-extraction`,
          { method: 'POST' }
        );
        if (!isApiSuccess(arcRes)) {
           toast({ title: `Failed pre-requisite for ${ep.season}E${ep.episode}`, status: 'error' });
           continue;
        }
      }

      toast({ title: `Event analysis for ${ep.season}E${ep.episode}`, status: 'info', duration: 2000 });
      await api.analyzeEpisodeEventDriven(seriesData.code, ep.season, ep.episode);
    }
    setIsSubmitting(false);
    toast({ title: 'Batch Event Driven Analysis completed', status: 'success' });
    await onRefresh?.();
  };

  const handleBatchDeleteNarrative = async () => {
    if (selectedEpisodesList.length === 0) return;
    if (!validateSequentialDeletion('narrative_arc_extraction_status')) return;
    if (!window.confirm("Delete Narrative Arc Extraction for selected episodes? This deletes arcs/progressions from DB and Vector Store.")) return;
    
    setIsSubmitting(true);
    // Delete in reverse chronological order to prevent intermediate state violations if interrupted
    const reversed = [...selectedEpisodesList].reverse();
    for (const ep of reversed) {
      if (ep.narrative_arc_extraction_status === 'not_processed' || ep.narrative_arc_extraction_status === 'missing_files') continue;
      await api.request(
        `/library/explorer/${seriesData.code}/${ep.season}/${ep.episode}/reset-narrative`,
        { method: 'POST' }
      );
    }
    setIsSubmitting(false);
    toast({ title: 'Batch Narrative Reset completed', status: 'success' });
    await onRefresh?.();
  };

  const handleBatchDeleteEventDriven = async () => {
    if (selectedEpisodesList.length === 0) return;
    if (!validateSequentialDeletion('event_driven_video_analysis_status')) return;
    if (!window.confirm("Delete Event-Driven Analysis for selected episodes? This deletes events and extracted video clips.")) return;
    
    setIsSubmitting(true);
    const reversed = [...selectedEpisodesList].reverse();
    for (const ep of reversed) {
      if (ep.event_driven_video_analysis_status === 'not_processed' || ep.event_driven_video_analysis_status === 'missing_files') continue;
      await api.resetEventDrivenAnalysis(seriesData.code, ep.season, ep.episode);
    }
    setIsSubmitting(false);
    toast({ title: 'Batch Event Reset completed', status: 'success' });
    await onRefresh?.();
  };

  const renderStatusIcon = (status: string | boolean) => {
    if (status === true || status === 'completed') return <Icon as={CheckCircleIcon} color="green.500" />;
    if (status === 'error') return <Icon as={WarningIcon} color="red.500" />;
    if (status === 'pending') return <Icon as={TimeIcon} color="yellow.500" />;
    return <Icon as={CloseIcon} color="gray.300" />;
  };

  return (
    <VStack align="stretch" spacing={6}>
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <HStack justify="space-between" align="center">
          <VStack align="left" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold" color="blue.600">{seriesData.display_name}</Text>
            <Text fontSize="sm" color="gray.500" fontWeight="medium">Analysis Engine Dashboard | {seriesData.code}</Text>
          </VStack>
          <Button size="sm" onClick={onSelectSeriesManager}>Series Manager</Button>
        </HStack>
      </Box>

      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <VStack align="stretch" spacing={4}>
          <HStack justify="space-between" align="center" flexWrap="wrap" gap={2}>
            <Text fontWeight="bold">Batch Actions ({selectedEpisodeIds.size} selected)</Text>
            <HStack spacing={2} flexWrap="wrap">
              <Button size="sm" colorScheme="teal" onClick={handleGenerateMissingFiles} isDisabled={selectedEpisodeIds.size === 0 || isSubmitting} isLoading={isSubmitting}>
                Generate Missing Files
              </Button>
              <Button size="sm" colorScheme="blue" onClick={handleBatchNarrativeExtraction} isDisabled={selectedEpisodeIds.size === 0 || isSubmitting} isLoading={isSubmitting}>
                Start Narrative Arc
              </Button>
              <Button size="sm" colorScheme="cyan" onClick={handleBatchEventDrivenAnalysis} isDisabled={selectedEpisodeIds.size === 0 || isSubmitting} isLoading={isSubmitting}>
                Start Event Driven
              </Button>
              <Button size="sm" colorScheme="red" variant="outline" onClick={handleBatchDeleteNarrative} isDisabled={selectedEpisodeIds.size === 0 || isSubmitting} isLoading={isSubmitting}>
                Delete Narrative Arc
              </Button>
              <Button size="sm" colorScheme="red" variant="solid" onClick={handleBatchDeleteEventDriven} isDisabled={selectedEpisodeIds.size === 0 || isSubmitting} isLoading={isSubmitting}>
                Delete Event Driven
              </Button>
            </HStack>
          </HStack>

          <Box overflowX="auto">
            <Table variant="simple" size="sm">
              <Thead>
                <Tr>
                  <Th><Checkbox isChecked={selectedEpisodeIds.size > 0 && selectedEpisodeIds.size === flatEpisodes.length} isIndeterminate={selectedEpisodeIds.size > 0 && selectedEpisodeIds.size < flatEpisodes.length} onChange={toggleAll} /></Th>
                  <Th>Season</Th>
                  <Th>Episode</Th>
                  <Th textAlign="center">Video</Th>
                  <Th textAlign="center">SRT</Th>
                  <Th textAlign="center">Plot</Th>
                  <Th textAlign="center">Narrative Arc Extraction</Th>
                  <Th textAlign="center">Event Driven Analysis</Th>
                </Tr>
              </Thead>
              <Tbody>
                {flatEpisodes.map((ep) => {
                  const id = `${ep.season}-${ep.episode}`;
                  return (
                    <Tr key={id} _hover={{ bg: 'gray.50' }}>
                      <Td><Checkbox isChecked={selectedEpisodeIds.has(id)} onChange={() => toggleSelection(id)} /></Td>
                      <Td>{ep.season}</Td>
                      <Td>{ep.episode}</Td>
                      <Td textAlign="center">{renderStatusIcon(ep.has_video_file)}</Td>
                      <Td textAlign="center">{renderStatusIcon(ep.has_srt_file)}</Td>
                      <Td textAlign="center">{renderStatusIcon(ep.has_plot_file)}</Td>
                      <Td textAlign="center">
                        <Tooltip label={ep.narrative_arc_extraction_status}>
                          <Box>{renderStatusIcon(ep.narrative_arc_extraction_status)}</Box>
                        </Tooltip>
                      </Td>
                      <Td textAlign="center">
                        <Tooltip label={ep.event_driven_video_analysis_status}>
                          <Box>{renderStatusIcon(ep.event_driven_video_analysis_status)}</Box>
                        </Tooltip>
                      </Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </Box>
        </VStack>
      </Box>
    </VStack>
  );
};
