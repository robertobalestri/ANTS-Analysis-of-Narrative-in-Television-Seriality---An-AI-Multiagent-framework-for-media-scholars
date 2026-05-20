import React, { useMemo, useRef, useCallback, useEffect, useState } from 'react';
import { Box, Text, Tooltip } from '@chakra-ui/react';
import type { EventDrivenAnalysisSnapshot, NarrativeEvent, ArcInfo } from '@/architecture/types';

// Arc colors (for row accents)
const ARC_COLORS = [
  '#E32017', '#FFD300', '#003688', '#008150',
  '#F3A9BB', '#A0A5A9', '#EE7C0E', '#B36305',
];

// Layout constants
const CELL_W = 98;
const CELL_H = 40;
const CELL_GAP = 4; // spacing between cells
const DIVIDER_W = 6;
const LABEL_W = 220; // arc label column width (increased to prevent cropping)

interface EventTimelineVisualizerProps {
  snapshot: EventDrivenAnalysisSnapshot;
  selectedEvent: NarrativeEvent | null;
  onSelectEvent: (event: NarrativeEvent) => void;
}

// Pre-compute the x-offset for each event column (accounts for episode dividers)
function computeColumnLayout(sortedEvents: NarrativeEvent[]) {
  const offsets: number[] = [];
  const dividerIndices = new Set<number>(); // indices where a divider appears BEFORE the column
  let x = 0;
  for (let i = 0; i < sortedEvents.length; i++) {
    if (i > 0 && sortedEvents[i].episode_ref !== sortedEvents[i - 1].episode_ref) {
      dividerIndices.add(i);
      x += DIVIDER_W;
    }
    offsets.push(x);
    x += CELL_W + CELL_GAP;
  }
  return { offsets, totalWidth: x, dividerIndices };
}

export const EventTimelineVisualizer: React.FC<EventTimelineVisualizerProps> = ({
  snapshot,
  selectedEvent,
  onSelectEvent,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Drag-to-scroll state
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartY = useRef(0);
  const scrollLeftStart = useRef(0);
  const scrollTopStart = useRef(0);
  const wasDraggedRef = useRef(false);
  const DRAG_THRESHOLD = 5;

  // Tooltip state
  const [tooltipInfo, setTooltipInfo] = useState<{
    x: number; y: number; arcTitle: string; present: boolean;
  } | null>(null);

  // Get arc info from snapshot or build fallback
  const arcs: ArcInfo[] = useMemo(() => {
    if (snapshot.arcs && snapshot.arcs.length > 0) {
      return snapshot.arcs;
    }
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
      if (a.episode_ref !== b.episode_ref) {
        return a.episode_ref.localeCompare(b.episode_ref);
      }
      return a.srt_start_index - b.srt_start_index;
    });
  }, [snapshot.events]);

  // Build arc -> events map
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

  // Column layout
  const columnLayout = useMemo(
    () => computeColumnLayout(sortedEvents),
    [sortedEvents]
  );

  const canvasWidth = columnLayout.totalWidth;
  const canvasHeight = arcs.length * (CELL_H + CELL_GAP);

  // ── Draw the canvas ──────────────────────────────────────────────────
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasWidth * dpr;
    canvas.height = canvasHeight * dpr;
    canvas.style.width = `${canvasWidth}px`;
    canvas.style.height = `${canvasHeight}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Draw cells
    for (let arcIdx = 0; arcIdx < arcs.length; arcIdx++) {
      const arc = arcs[arcIdx];
      const eventIds = arcEventsMap.get(arc.id) || new Set();
      const rowY = arcIdx * (CELL_H + CELL_GAP);

      for (let evIdx = 0; evIdx < sortedEvents.length; evIdx++) {
        const event = sortedEvents[evIdx];
        const cellX = columnLayout.offsets[evIdx];
        const hasArc = eventIds.has(event.id);
        const isSelected = selectedEvent?.id === event.id;

        // Cell background
        ctx.fillStyle = hasArc ? '#C6F6D5' : '#FED7D7';
        ctx.fillRect(cellX, rowY, CELL_W, CELL_H);

        // Cell border
        ctx.strokeStyle = hasArc ? '#38A169' : '#FC8181';
        ctx.lineWidth = isSelected ? 3 : 2;
        ctx.strokeRect(cellX + 1, rowY + 1, CELL_W - 2, CELL_H - 2);

        // Selected highlight
        if (isSelected) {
          ctx.strokeStyle = '#3182CE';
          ctx.lineWidth = 3;
          ctx.strokeRect(cellX, rowY, CELL_W, CELL_H);
        }

        // Symbol
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        if (hasArc) {
          ctx.fillStyle = '#38A169';
          ctx.font = 'bold 16px sans-serif';
          ctx.fillText('✓', cellX + CELL_W / 2, rowY + CELL_H / 2);
        } else {
          ctx.fillStyle = '#FC8181';
          ctx.font = '16px sans-serif';
          ctx.fillText('—', cellX + CELL_W / 2, rowY + CELL_H / 2);
        }
      }
    }

    // Draw episode dividers (black vertical stripes across all rows)
    ctx.fillStyle = '#000000';
    for (const divIdx of columnLayout.dividerIndices) {
      const divX = columnLayout.offsets[divIdx] - DIVIDER_W;
      ctx.fillRect(divX, 0, DIVIDER_W, canvasHeight);
    }
  }, [arcs, sortedEvents, arcEventsMap, columnLayout, canvasWidth, canvasHeight, selectedEvent]);

  useEffect(() => {
    drawCanvas();
  }, [drawCanvas]);

  // ── Hit-test: convert mouse position to (eventIndex, arcIndex) ──────
  const hitTest = useCallback(
    (clientX: number, clientY: number): { eventIdx: number; arcIdx: number } | null => {
      const canvas = canvasRef.current;
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;

      const arcIdx = Math.floor(y / (CELL_H + CELL_GAP));
      if (arcIdx < 0 || arcIdx >= arcs.length) return null;

      // Binary search for the event column
      for (let i = 0; i < sortedEvents.length; i++) {
        const colX = columnLayout.offsets[i];
        if (x >= colX && x < colX + CELL_W) {
          return { eventIdx: i, arcIdx };
        }
      }
      return null;
    },
    [arcs.length, sortedEvents.length, columnLayout.offsets]
  );

  // ── Canvas mouse handlers ──────────────────────────────────────────
  const handleCanvasClick = useCallback(
    (e: React.MouseEvent) => {
      if (wasDraggedRef.current) return;
      const hit = hitTest(e.clientX, e.clientY);
      if (hit) {
        onSelectEvent(sortedEvents[hit.eventIdx]);
      }
    },
    [hitTest, sortedEvents, onSelectEvent]
  );

  const handleCanvasMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const hit = hitTest(e.clientX, e.clientY);
      if (hit) {
        const arc = arcs[hit.arcIdx];
        const event = sortedEvents[hit.eventIdx];
        const eventIds = arcEventsMap.get(arc.id) || new Set();
        const present = eventIds.has(event.id);
        // Position tooltip near cursor
        const container = scrollContainerRef.current;
        if (container) {
          const containerRect = container.getBoundingClientRect();
          setTooltipInfo({
            x: e.clientX - containerRect.left + 12,
            y: e.clientY - containerRect.top - 10,
            arcTitle: arc.title,
            present,
          });
        }
      } else {
        setTooltipInfo(null);
      }
    },
    [hitTest, arcs, sortedEvents, arcEventsMap]
  );

  const handleCanvasMouseLeave = useCallback(() => {
    setTooltipInfo(null);
  }, []);

  // ── Drag-to-scroll handlers (on outer container) ───────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    dragStartX.current = e.clientX;
    dragStartY.current = e.clientY;
    const container = scrollContainerRef.current;
    if (container) {
      scrollLeftStart.current = container.scrollLeft;
      scrollTopStart.current = container.scrollTop;
    }
    setIsDragging(true);
    wasDraggedRef.current = false;
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStartX.current;
      const dy = e.clientY - dragStartY.current;
      if (!wasDraggedRef.current && Math.sqrt(dx * dx + dy * dy) > DRAG_THRESHOLD) {
        wasDraggedRef.current = true;
      }
      const container = scrollContainerRef.current;
      if (container) {
        container.scrollLeft = scrollLeftStart.current - dx;
        container.scrollTop = scrollTopStart.current - dy;
      }
    },
    [isDragging]
  );

  const handleMouseUpOrLeave = useCallback(() => {
    setIsDragging(false);
    setTimeout(() => {
      wasDraggedRef.current = false;
    }, 0);
  }, []);

  // ── Header click handler ───────────────────────────────────────────
  const handleHeaderClick = useCallback(
    (event: NarrativeEvent) => {
      if (wasDraggedRef.current) return;
      onSelectEvent(event);
    },
    [onSelectEvent]
  );

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
      ref={scrollContainerRef}
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
      position="relative"
    >
      {/* Floating tooltip (single div, repositioned on hover) */}
      {tooltipInfo && (
        <div
          ref={tooltipRef}
          style={{
            position: 'absolute',
            left: tooltipInfo.x,
            top: tooltipInfo.y,
            background: '#1A202C',
            color: 'white',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            pointerEvents: 'none',
            zIndex: 100,
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          }}
        >
          <strong>{tooltipInfo.arcTitle}</strong>
          <br />
          {tooltipInfo.present ? 'Present in event' : 'Not in this event'}
        </div>
      )}

      {/* Content wrapper with min-width to enable horizontal scroll */}
      <div style={{ width: `${LABEL_W + canvasWidth}px` }}>

        {/* ── Header row ────────────────────────────────────────────── */}
        <div style={{ position: 'relative', height: '115px', marginBottom: '8px' }}>
          {/* Empty corner (matches arc label width) */}
          <div
            style={{
              width: LABEL_W,
              minWidth: LABEL_W,
              position: 'sticky',
              left: 0,
              zIndex: 5,
              background: '#f8f9fa',
              height: '100%',
            }}
          />
          {/* Episode dividers drawn in header */}
          {Array.from(columnLayout.dividerIndices).map((divIdx) => {
            const divX = columnLayout.offsets[divIdx] - DIVIDER_W;
            return (
              <div
                key={`div-${divIdx}`}
                style={{
                  position: 'absolute',
                  left: LABEL_W + divX,
                  width: DIVIDER_W,
                  background: 'black',
                  height: '100%',
                }}
              />
            );
          })}
          {/* Event column headers */}
          {sortedEvents.map((event, idx) => {
            const isSelected = selectedEvent?.id === event.id;
            const cellX = columnLayout.offsets[idx];
            return (
              <div
                key={event.id}
                style={{
                  position: 'absolute',
                  left: LABEL_W + cellX,
                  width: CELL_W,
                  cursor: 'pointer',
                  top: 0,
                }}
                onClick={() => handleHeaderClick(event)}
              >
                {/* Clapperboard card */}
                <div
                  style={{
                    height: 56,
                    background: '#2D3748',
                    color: 'white',
                    borderRadius: 6,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLDivElement).style.background = '#4A5568';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLDivElement).style.background = '#2D3748';
                  }}
                >
                  <span style={{ fontSize: 14, marginBottom: 2 }}>🎬</span>
                  <span style={{ fontWeight: 'bold', color: '#90CDF4' }}>
                    {event.episode_ref}
                  </span>
                  <span style={{ color: '#A0AEC0', fontSize: 8 }}>
                    {event.srt_start_time}
                  </span>
                </div>
                {/* Event type + content mini-card */}
                <div
                  style={{
                    marginTop: 4,
                    padding: '3px 4px',
                    background: isSelected ? '#BEE3F8' : 'white',
                    borderRadius: 4,
                    border: `1px solid ${isSelected ? '#3182CE' : '#E2E8F0'}`,
                    textAlign: 'center',
                    fontSize: 8,
                    lineHeight: '1.2',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      display: 'inline-block',
                      background: '#EDF2F7',
                      borderRadius: 3,
                      padding: '1px 4px',
                      fontSize: 7,
                      fontWeight: 600,
                      marginBottom: 2,
                      color: '#4A5568',
                    }}
                  >
                    {event.event_type}
                  </div>
                  <div
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      color: '#2D3748',
                    }}
                  >
                    {event.content}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Matrix body: arc labels + canvas ───────────────────────── */}
        <div style={{ display: 'flex' }}>
          {/* Arc labels (sticky left) */}
          <div
            style={{
              width: LABEL_W,
              minWidth: LABEL_W,
              position: 'sticky',
              left: 0,
              zIndex: 4,
              background: '#f8f9fa',
            }}
          >
            {arcs.map((arc, arcIdx) => {
              const arcColor = arc.color || ARC_COLORS[arcIdx % ARC_COLORS.length];
              return (
                <Tooltip key={arc.id} label={arc.title} placement="right">
                  <div
                    style={{
                      height: CELL_H,
                      marginBottom: CELL_GAP,
                      background: arcColor,
                      color: 'white',
                      borderRadius: 6,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 10,
                      fontWeight: 'bold',
                      padding: '4px 8px',
                      textAlign: 'center',
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                      lineHeight: '1.2',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
                    }}
                  >
                    {arc.title}
                  </div>
                </Tooltip>
              );
            })}
          </div>

          {/* Canvas */}
          <canvas
            ref={canvasRef}
            style={{
              display: 'block',
              cursor: isDragging ? 'grabbing' : 'pointer',
            }}
            onClick={handleCanvasClick}
            onMouseMove={handleCanvasMouseMove}
            onMouseLeave={handleCanvasMouseLeave}
          />
        </div>

        {/* Legend */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 16,
            marginTop: 16,
            background: 'white',
            padding: '8px 16px',
            borderRadius: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div
              style={{
                width: 20,
                height: 20,
                background: '#C6F6D5',
                border: '2px solid #38A169',
                borderRadius: 4,
              }}
            />
            <span style={{ fontSize: 12 }}>Arc present in event</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div
              style={{
                width: 20,
                height: 20,
                background: '#FED7D7',
                border: '2px solid #FC8181',
                borderRadius: 4,
              }}
            />
            <span style={{ fontSize: 12 }}>Arc absent</span>
          </div>
          <span style={{ fontSize: 12, color: '#718096' }}>
            {totalEvents} events × {arcs.length} arcs
          </span>
        </div>
      </div>
    </Box>
  );
};