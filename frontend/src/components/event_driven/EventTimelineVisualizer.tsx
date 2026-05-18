import React, { useState, useMemo, useRef, useCallback } from 'react';
import { Box, Text, Badge, HStack, VStack, Tooltip, IconButton, Flex } from '@chakra-ui/react';
import type { EventDrivenAnalysisSnapshot, NarrativeEvent, ArcInfo } from '@/architecture/types';

// Arc colors (for row accents)
const ARC_COLORS = [
  '#E32017', '#FFD300', '#003688', '#008150',
  '#F3A9BB', '#A0A5A9', '#EE7C0E', '#B36305',
];

interface VideoClipProps {
  clipPath?: string;
  event: NarrativeEvent;
  series: string;
}

const VideoClip: React.FC<VideoClipProps> = ({ clipPath, event, series }) => {
  const [playing, setPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Extract relative path from absolute path (e.g., "S01/E01/clips/event.mp4")
  const clipParts = useMemo(() => {
    if (!clipPath) return null;
    // clipPath may be absolute like "D:/DATA/.../data/series/S01/E01/clips/event.mp4"
    const sep = clipPath.includes('/') ? '/' : '\\';
    const parts = clipPath.split(sep);
    const clipsIdx = parts.indexOf('clips');
    if (clipsIdx !== -1 && clipsIdx >= 3) {
      return {
        season: parts[clipsIdx - 2],   // "S01"
        episode: parts[clipsIdx - 1],  // "E01"
        filename: parts[clipsIdx + 1], // "event.mp4"
      };
    }
    // Fallback: derive from event.episode_ref like "S01E01"
    const epMatch = event.episode_ref.match(/^(S\d+)(E\d+)$/);
    if (epMatch) {
      return {
        season: epMatch[1],
        episode: epMatch[2],
        filename: clipPath.split(sep).pop() || '',
      };
    }
    return null;
  }, [clipPath, event.episode_ref]);

  const clipUrl = clipParts
    ? `/api/events/${series}/clips/${clipParts.season}/${clipParts.episode}/clips/${clipParts.filename}`
    : null;

  if (!clipUrl) {
    return (
      <Box
        w="100%"
        h="80px"
        bg="gray.100"
        borderRadius="md"
        display="flex"
        alignItems="center"
        justifyContent="center"
        border={`2px solid ${ARC_COLORS[0]}`}
      >
        <VStack spacing={0}>
          <Text fontSize="9px" color="gray.500" fontWeight="bold">{event.episode_ref}</Text>
          <Text fontSize="8px" color="gray.400">{event.srt_start_time}</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box position="relative" w="100%">
      {!playing ? (
        <Box
          position="relative"
          cursor="pointer"
          onClick={() => setPlaying(true)}
          borderRadius="md"
          overflow="hidden"
          border={`2px solid ${ARC_COLORS[0]}`}
          bg="black"
        >
          <video
            src={clipUrl}
            style={{ width: '100%', height: '80px', objectFit: 'cover', display: 'block' }}
          />
          <Box
            position="absolute"
            top="50%"
            left="50%"
            transform="translate(-50%, -50%)"
            bg="blackAlpha.700"
            borderRadius="full"
            p={2}
          >
            <Text fontSize="16px">▶</Text>
          </Box>
          <Box position="absolute" bottom={0} left={0} right={0} bg="blackAlpha.700" p={1}>
            <Text fontSize="8px" color="white">{event.srt_start_time}</Text>
          </Box>
        </Box>
      ) : (
        <Box position="relative" borderRadius="md" overflow="hidden" border={`2px solid ${ARC_COLORS[0]}`}>
          <IconButton
            aria-label="Close video"
            icon={<Text fontSize="10px">✕</Text>}
            size="xs"
            position="absolute"
            top={1}
            right={1}
            zIndex={10}
            bg="blackAlpha.700"
            color="white"
            onClick={() => setPlaying(false)}
          />
          <video
            ref={videoRef}
            src={clipUrl}
            controls
            autoPlay
            style={{ width: '100%', height: '80px', objectFit: 'contain', display: 'block', background: 'black' }}
          />
        </Box>
      )}
    </Box>
  );
};

export const EventTimelineVisualizer: React.FC<EventTimelineVisualizerProps> = ({
  snapshot,
  selectedEvent,
  onSelectEvent,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartY = useRef(0);
  const scrollLeftRef = useRef(0);
  const scrollTopRef = useRef(0);
  const wasDraggedRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const DRAG_THRESHOLD = 5;

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    // Only drag with left click
    if (e.button !== 0) return;
    dragStartX.current = e.clientX;
    dragStartY.current = e.clientY;
    scrollLeftRef.current = e.currentTarget.scrollLeft;
    scrollTopRef.current = e.currentTarget.scrollTop;
    setIsDragging(true);
    wasDraggedRef.current = false;
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const container = e.currentTarget;
    const dx = e.clientX - dragStartX.current;
    const dy = e.clientY - dragStartY.current;
    if (!wasDraggedRef.current && Math.sqrt(dx * dx + dy * dy) > DRAG_THRESHOLD) {
      wasDraggedRef.current = true;
    }
    container.scrollLeft = scrollLeftRef.current - dx;
    container.scrollTop = scrollTopRef.current - dy;
  }, [isDragging]);

  const handleMouseUpOrLeave = useCallback(() => {
    setIsDragging(false);
    // Keep wasDraggedRef true briefly so child onClick sees it and ignores click actions during drag
    setTimeout(() => { wasDraggedRef.current = false; }, 0);
  }, []);

  // Get arc info from snapshot or build fallback
  const arcs: ArcInfo[] = useMemo(() => {
    if (snapshot.arcs && snapshot.arcs.length > 0) {
      return snapshot.arcs;
    }
    // Fallback: group events by episode
    const episodeMap = new Map<string, NarrativeEvent[]>();
    for (const event of snapshot.events) {
      const ep = event.episode_ref;
      if (!episodeMap.has(ep)) episodeMap.set(ep, []);
      episodeMap.get(ep)!.push(event);
    }
    const fallbackArcs: ArcInfo[] = [];
    let idx = 0;
    for (const [ep] of episodeMap) {
      fallbackArcs.push({
        id: `episode-${ep}`,
        title: ep,
        color: ARC_COLORS[idx % ARC_COLORS.length],
      });
      idx++;
    }
    return fallbackArcs;
  }, [snapshot.arcs, snapshot.events]);

  // Sort events chronologically
  const sortedEvents = useMemo(() => {
    return [...snapshot.events].sort((a, b) => {
      // Sort by episode, then by srt_start_index
      if (a.episode_ref !== b.episode_ref) {
        return a.episode_ref.localeCompare(b.episode_ref);
      }
      return a.srt_start_index - b.srt_start_index;
    });
  }, [snapshot.events]);

  // Build arc -> events map (for quick lookup)
  const arcEventsMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const arc of arcs) {
      map.set(arc.id, new Set());
    }
    for (const event of snapshot.events) {
      if (event.arc_ids && event.arc_ids.length > 0) {
        for (const arcId of event.arc_ids) {
          if (map.has(arcId)) {
            map.get(arcId)!.add(event.id);
          }
        }
      }
    }
    return map;
  }, [arcs, snapshot.events]);

  const totalEvents = sortedEvents.length;

  if (totalEvents === 0) {
    return (
      <Box p={4} textAlign="center">
        <Text color="gray.500">No events to display</Text>
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      w="100%"
      overflowX="auto"
      overflowY="auto"
      bg="#f8f9fa"
      borderRadius="lg"
      p={2}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUpOrLeave}
      onMouseLeave={handleMouseUpOrLeave}
      cursor={isDragging ? 'grabbing' : 'grab'}
      style={{ userSelect: 'none' }}
    >
      {/* Main matrix grid */}
      <Box minW={`${120 + totalEvents * 100}px`}>
        {/* Header row: Arc labels + Event columns */}
        <Flex mb={2}>
          {/* Empty corner cell */}
          <Box w="120px" minW="120px" />

          {/* Event columns with video headers */}
          <HStack spacing={1} flex={1}>
            {sortedEvents.map((event) => (
              <Box key={event.id} w="98px" minW="98px">
                <VideoClip
                  clipPath={event.clip_path}
                  event={event}
                  series={snapshot.series}
                />
                <Box
                  mt={1}
                  p={1}
                  bg={selectedEvent?.id === event.id ? 'blue.100' : 'white'}
                  borderRadius="sm"
                  border="1px solid"
                  borderColor={selectedEvent?.id === event.id ? 'blue.400' : 'gray.200'}
                  cursor="pointer"
                  onClick={() => { if (wasDraggedRef.current) return; onSelectEvent(event); }}
                  _hover={{ borderColor: 'blue.300' }}
                >
                  <VStack spacing={0} align="center">
                    <Badge fontSize="8px" colorScheme="gray" mb={0.5}>
                      {event.event_type}
                    </Badge>
                    <Text fontSize="8px" noOfLines={2} textAlign="center" lineHeight="tight">
                      {event.content}
                    </Text>
                    <Text fontSize="7px" color="gray.400" mt={0.5}>
                      {event.srt_start_time}
                    </Text>
                  </VStack>
                </Box>
              </Box>
            ))}
          </HStack>
        </Flex>

        {/* Arc rows */}
        {arcs.map((arc, arcIdx) => {
          const arcColor = arc.color || ARC_COLORS[arcIdx % ARC_COLORS.length];
          const eventIds = arcEventsMap.get(arc.id) || new Set();

          return (
            <Flex key={arc.id} mb={1} align="center">
              {/* Arc label (left) */}
              <Tooltip label={arc.title} placement="left">
                <Box
                  w="120px"
                  minW="120px"
                  bg={arcColor}
                  color="white"
                  px={2}
                  py={2}
                  borderRadius="md"
                  fontSize="10px"
                  fontWeight="bold"
                  textAlign="center"
                  boxShadow="sm"
                  overflow="hidden"
                  textOverflow="ellipsis"
                  whiteSpace="nowrap"
                >
                  {arc.title}
                </Box>
              </Tooltip>

              {/* Event cells for this arc */}
              <HStack spacing={1} flex={1}>
                {sortedEvents.map((event) => {
                  const hasArc = eventIds.has(event.id);
                  const isMulti = event.arc_ids && event.arc_ids.length > 1;

                  return (
                    <Tooltip
                      key={event.id}
                      label={
                        <VStack align="start" spacing={0} p={1}>
                          <Text fontWeight="bold" fontSize="10px">{arc.title}</Text>
                          <Text fontSize="9px">{hasArc ? 'Present in event' : 'Not in this event'}</Text>
                        </VStack>
                      }
                    >
                      <Box
                        w="98px"
                        minW="98px"
                        h="40px"
                        bg={hasArc ? 'green.100' : 'red.100'}
                        border={`2px solid ${hasArc ? 'green.400' : 'red.300'}`}
                        borderRadius="md"
                        display="flex"
                        alignItems="center"
                        justifyContent="center"
                        cursor="pointer"
                        transition="all 0.15s"
                        _hover={{ transform: 'scale(1.05)', boxShadow: 'md' }}
                        onClick={() => { if (wasDraggedRef.current) return; onSelectEvent(event); }}
                      >
                        {hasArc ? (
                          <VStack spacing={0}>
                            <Text fontSize="14px" color="green.600">✓</Text>
                            {isMulti && (
                              <HStack spacing={0.5} wrap="wrap" justify="center" maxW="90px">
                                {(event.arc_ids || []).slice(0, 8).map((aid, i) => {
                                  const c = arcs.find(a => a.id === aid)?.color || ARC_COLORS[0];
                                  return <Box key={i} w="6px" h="3px" bg={c} borderRadius="1px" />;
                                })}
                              </HStack>
                            )}
                          </VStack>
                        ) : (
                          <Text fontSize="14px" color="red.400">—</Text>
                        )}
                      </Box>
                    </Tooltip>
                  );
                })}
              </HStack>
            </Flex>
          );
        })}
      </Box>

      {/* Legend */}
      <HStack mt={4} spacing={4} justify="center" bg="white" p={2} borderRadius="md">
        <HStack spacing={1}>
          <Box w="20px" h="20px" bg="green.100" border="2px solid green.400" borderRadius="md" />
          <Text fontSize="xs">Arc present in event</Text>
        </HStack>
        <HStack spacing={1}>
          <Box w="20px" h="20px" bg="red.100" border="2px solid red.300" borderRadius="md" />
          <Text fontSize="xs">Arc absent</Text>
        </HStack>
        <Text fontSize="xs" color="gray.500">
          {totalEvents} events × {arcs.length} arcs
        </Text>
      </HStack>
    </Box>
  );
};

interface EventTimelineVisualizerProps {
  snapshot: EventDrivenAnalysisSnapshot;
  selectedEvent: NarrativeEvent | null;
  onSelectEvent: (event: NarrativeEvent) => void;
}