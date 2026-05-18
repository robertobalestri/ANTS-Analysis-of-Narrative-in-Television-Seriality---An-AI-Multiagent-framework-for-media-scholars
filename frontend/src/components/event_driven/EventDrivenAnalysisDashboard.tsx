import React, { useState, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  useToast,
  useColorModeValue,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Badge,
} from '@chakra-ui/react';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';
import type { EventDrivenAnalysisSnapshot, NarrativeEvent } from '@/architecture/types';
import { EventTimelineVisualizer } from './EventTimelineVisualizer';

interface EventDrivenAnalysisDashboardProps {
  series: string;
}

const api = ApiClient.getInstance();

export const EventDrivenAnalysisDashboard: React.FC<EventDrivenAnalysisDashboardProps> = ({ series }) => {
  const toast = useToast();
  const [snapshot, setSnapshot] = useState<EventDrivenAnalysisSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<NarrativeEvent | null>(null);
  const bgColor = useColorModeValue('white', 'gray.800');

  const loadSnapshot = useCallback(async () => {
    if (!series) return;
    setLoading(true);
    try {
      const res = await api.getEventDrivenAnalysisSnapshot(series);
      if (isApiSuccess(res)) {
        setSnapshot(res.data);
      }
    } catch (err) {
      toast({
        title: 'Failed to load events',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  }, [series, toast]);

  // Load on mount
  React.useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  const totalEvents = snapshot?.events?.length ?? 0;
  const totalArcs = snapshot?.arcs?.length ?? 0;

  return (
    <Box h="100%" display="flex" flexDirection="column" bg={bgColor} overflow="hidden">
      {/* Header */}
      <Box px={4} py={3} borderBottom="1px solid" borderColor="gray.200">
        <HStack justify="space-between">
          <VStack align="start" spacing={0}>
            <Heading size="md">Event-Driven Narrative Analysis</Heading>
            <HStack spacing={2} mt={1}>
              {totalEvents > 0 && (
                <>
                  <Badge colorScheme="blue">{totalEvents} events</Badge>
                  <Badge colorScheme="purple">{totalArcs} arcs</Badge>
                </>
              )}
            </HStack>
          </VStack>
          <HStack>
            <Text fontSize="sm" color="gray.500" mr={2}>{series}</Text>
          </HStack>
        </HStack>
      </Box>

      {/* Main content */}
      <Box flex={1} overflow="hidden" display="flex" flexDirection="column">
        <Box flex={1} overflow="auto" p={2}>
          {loading ? (
            <Box p={4} textAlign="center">
              <Text color="gray.500">Loading events...</Text>
            </Box>
          ) : totalEvents === 0 ? (
            <Box p={8} textAlign="center">
              <VStack spacing={3}>
                <Text color="gray.500" fontSize="lg">No events yet</Text>
                <Text color="gray.400" fontSize="sm">
                  Run event analysis from the Analysis Engine
                </Text>
              </VStack>
            </Box>
          ) : (
            <EventTimelineVisualizer
              snapshot={snapshot!}
              selectedEvent={selectedEvent}
              onSelectEvent={setSelectedEvent}
            />
          )}
        </Box>
      </Box>

      {/* Event Detail Modal */}
      <Modal isOpen={!!selectedEvent} onClose={() => setSelectedEvent(null)} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <Badge colorScheme="blue">{selectedEvent?.episode_ref}</Badge>
              <Text fontSize="sm" fontWeight="normal" color="gray.500">
                {selectedEvent?.srt_start_time}
              </Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            {selectedEvent && (
              <VStack align="stretch" spacing={4}>
                <Box>
                  <Text fontSize="sm" fontWeight="bold" mb={1}>Content</Text>
                  <Text>{selectedEvent.content}</Text>
                </Box>
                <Box>
                  <Text fontSize="sm" fontWeight="bold" mb={1}>Characters</Text>
                  <HStack flexWrap="wrap">
                    {selectedEvent.characters.map((char, i) => (
                      <Badge key={i} mr={1} mb={1}>{char}</Badge>
                    ))}
                  </HStack>
                </Box>
                {selectedEvent.arc_ids && selectedEvent.arc_ids.length > 0 && (
                  <Box>
                    <Text fontSize="sm" fontWeight="bold" mb={1}>Narrative Arcs</Text>
                    <HStack flexWrap="wrap">
                      {selectedEvent.arc_ids.map((arcId) => {
                        const arc = snapshot?.arcs?.find(a => a.id === arcId);
                        return (
                          <Badge key={arcId} bg={arc?.color || 'gray.400'} color="white">
                            {arc?.title || arcId}
                          </Badge>
                        );
                      })}
                    </HStack>
                  </Box>
                )}
                <Box>
                  <Text fontSize="sm" fontWeight="bold" mb={1}>Event Type</Text>
                  <Badge>{selectedEvent.event_type}</Badge>
                </Box>
              </VStack>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};
