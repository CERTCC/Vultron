import { useState, useCallback, useRef } from 'react'
import type { DemoState } from './types'
import './App.css'
import { LANE_HEIGHT, LANE_HEIGHT_COLLAPSED, ACTOR_PANEL_WIDTH, NODE_COLORS, NODE_HEIGHT, NODE_WIDTH, NODE_HEIGHT_COLLAPSED, NODE_ANIMATION_MS, getVendorNodeColors } from './constants'
import { ActorPanel, AnimatedNode } from './components'
import { getActiveLanes } from './state/participantHelpers'
import {
  parseCaseLedger,
  normalizeLedger,
  type CaseLedgerEntry,
} from './utils/caseLedgerParser'
import { buildTimelineFromCaseLedger } from './utils/caseLedgerMapper'
// The committed sample case ledger, imported raw from the repo root (Vite serves
// it via `server.fs.allow`, the same mechanism protocol.ts uses for
// protocol_states.json — see vite.config.ts / ui/CLAUDE.md §9). A plain
// fetch('/devlogs/…') would resolve against ui/ as the web root and 404, so we
// import the text at build time instead. All three folders hold the byte-identical
// shared ledger; dedup-by-entryHash (in normalizeLedger) makes loading all safe,
// so importing one copy is sufficient and avoids redundant bundling.
import sampleLedgerRaw from '../../devlogs/two-actor/case-actor/urn_uuid_b9e6d36c-8f90-46bc-8bf7-a36446738f39-case-ledger.jsonl?raw'
// Hand-authored fixture with two deliberate protocol violations (RM re-validate,
// EM re-terminate) to exercise the red ⚠️ violation flagging. See
// devlogs/synthetic/README.md for the entry-by-entry expected result.
import violationLedgerRaw from '../../devlogs/synthetic/violations-case-ledger.jsonl?raw'
// Three-party container demo: finder + two vendors (vendor invites vendor2). These
// logs are NOT verified for protocol validity — a good stress test for the
// violation flagging. The case-actor copy is the coordinator's authoritative view
// (all four folder copies carry the same 19 entries; they differ only per
// perspective, so we load one copy rather than relying on entryHash dedup).
import fvvLedgerRaw from '../../devlogs/fvv/case-actor/urn_uuid_4e4ee04a-6503-495d-ba34-50bcce4ebc18-case-ledger.jsonl?raw'

type NodePalette = { decision: string; decisionHover: string; consequence: string; consequenceHover: string }

/**
 * Node color palette for a participant id. Handles any `vendor-N` (via the
 * cycling vendor palette), plus finder and caseactor; falls back to finder's
 * palette for anything unrecognized.
 */
function nodeColorsFor(participantId: string): NodePalette {
  if (participantId === 'finder') return NODE_COLORS.finder
  if (participantId === 'caseactor') return NODE_COLORS.caseactor
  const m = participantId.match(/^vendor-(\d+)$/)
  if (m) return getVendorNodeColors(parseInt(m[1], 10))
  return NODE_COLORS.finder
}

function AppLogReplay() {
  const [demoState, setDemoState] = useState<DemoState | null>(null)
  const [accumulatedEntries, setAccumulatedEntries] = useState<CaseLedgerEntry[]>([])
  const [uploadCount, setUploadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hoveredEvent, setHoveredEvent] = useState<string | null>(null)
  const [eventLogCollapsed, setEventLogCollapsed] = useState(false)
  const [currentEventIndex, setCurrentEventIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [collapsedParticipants, setCollapsedParticipants] = useState<Set<string>>(new Set())
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const sidebarScrollRef = useRef<HTMLDivElement>(null)
  const playIntervalRef = useRef<number | null>(null)

  // Build (or rebuild) the replay state from a full set of ledger entries.
  const rebuildFromEntries = useCallback((allEntries: CaseLedgerEntry[]) => {
    const normalized = normalizeLedger(allEntries)
    const state = buildTimelineFromCaseLedger(normalized)
    setDemoState(state)
    setCurrentEventIndex(0)
  }, [])

  // Handle file input - accumulates entries from multiple uploads
  const handleFileUpload = useCallback(async (files: FileList | null, shouldAccumulate = true) => {
    if (!files || files.length === 0) return

    setLoading(true)
    setError(null)

    try {
      const newEntries: CaseLedgerEntry[] = []

      // Read all uploaded files
      for (let i = 0; i < files.length; i++) {
        const content = await files[i].text()
        newEntries.push(...parseCaseLedger(content))
      }

      // Either accumulate or replace
      const allEntries = shouldAccumulate ? [...accumulatedEntries, ...newEntries] : newEntries
      setAccumulatedEntries(allEntries)
      setUploadCount(prev => prev + 1)

      rebuildFromEntries(allEntries)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load log files')
      console.error('Error processing log files:', err)
    } finally {
      setLoading(false)
    }
  }, [accumulatedEntries, rebuildFromEntries])

  // Load a committed ledger from its raw text (no file picker needed). Shared by
  // the happy-path sample and the synthetic violation fixture.
  const loadRawLedger = useCallback((raw: string, label: string) => {
    setLoading(true)
    setError(null)

    try {
      const allEntries = parseCaseLedger(raw)
      if (allEntries.length === 0) {
        throw new Error(`${label} was empty — try file upload instead.`)
      }
      setAccumulatedEntries(allEntries)
      setUploadCount(prev => prev + 1)
      rebuildFromEntries(allEntries)
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load ${label}`)
      console.error(`Error loading ${label}:`, err)
    } finally {
      setLoading(false)
    }
  }, [rebuildFromEntries])

  const handleLoadSample = useCallback(
    () => loadRawLedger(sampleLedgerRaw, 'sample logs'),
    [loadRawLedger]
  )
  const handleLoadViolationSample = useCallback(
    () => loadRawLedger(violationLedgerRaw, 'violation sample'),
    [loadRawLedger]
  )
  const handleLoadFvv = useCallback(
    () => loadRawLedger(fvvLedgerRaw, 'FVV logs'),
    [loadRawLedger]
  )

  // Reset everything
  const handleReset = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
    setDemoState(null)
    setAccumulatedEntries([])
    setUploadCount(0)
    setCurrentEventIndex(0)
    setError(null)
  }, [])

  // Playback controls
  const handlePlay = useCallback(() => {
    if (!demoState) return
    setIsPlaying(true)

    playIntervalRef.current = window.setInterval(() => {
      setCurrentEventIndex(prev => {
        if (prev >= demoState.timelineEvents.length - 1) {
          if (playIntervalRef.current) {
            clearInterval(playIntervalRef.current)
            playIntervalRef.current = null
          }
          setIsPlaying(false)
          return prev
        }
        return prev + 1
      })
      // Wait for the slide-in animation to finish (plus a small settle margin)
      // before revealing the next event, so no event starts mid-animation.
    }, NODE_ANIMATION_MS + 300)
  }, [demoState])

  const handlePause = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
  }, [])

  const handleStepForward = useCallback(() => {
    if (!demoState) return
    setCurrentEventIndex(prev => Math.min(prev + 1, demoState.timelineEvents.length - 1))
  }, [demoState])

  const handleStepBackward = useCallback(() => {
    setCurrentEventIndex(prev => Math.max(prev - 1, 0))
  }, [])

  const handleRewind = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current)
      playIntervalRef.current = null
    }
    setIsPlaying(false)
    setCurrentEventIndex(0)
  }, [])

  // Toggle a participant lane between full and collapsed height.
  const toggleParticipantCollapse = useCallback((participantId: string) => {
    setCollapsedParticipants(prev => {
      const next = new Set(prev)
      if (next.has(participantId)) next.delete(participantId)
      else next.add(participantId)
      return next
    })
  }, [])

  // Sync scrolling between timeline and sidebar
  const handleTimelineScroll = useCallback(() => {
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      sidebarScrollRef.current.scrollTop = timelineScrollRef.current.scrollTop
    }
  }, [])

  const handleSidebarScroll = useCallback(() => {
    if (timelineScrollRef.current && sidebarScrollRef.current) {
      timelineScrollRef.current.scrollTop = sidebarScrollRef.current.scrollTop
    }
  }, [])

  // If no state loaded, show file upload UI
  if (!demoState) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        padding: '2rem',
        background: '#f5f5f5',
      }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          maxWidth: '600px',
          textAlign: 'center',
        }}>
          <h2 style={{ marginTop: 0, color: '#0d47a1' }}>Log Replay Demo</h2>
          <p style={{ color: '#666', marginBottom: '0.5rem' }}>
            Upload participant JSONL log files to visualize the Vultron protocol execution.
          </p>

          {uploadCount > 0 && accumulatedEntries.length > 0 && (
            <div style={{
              background: '#e8f5e9',
              border: '1px solid #4caf50',
              borderRadius: '4px',
              padding: '0.75rem 1rem',
              margin: '1rem 0',
              color: '#2e7d32',
            }}>
              ✓ Loaded {accumulatedEntries.length} log entries from {uploadCount} upload(s)
            </div>
          )}

          {/* Primary action: load the committed sample case ledger directly */}
          <button
            onClick={handleLoadSample}
            style={{
              display: 'block',
              margin: '1.5rem auto 0.5rem',
              padding: '1rem 2rem',
              background: '#2e7d32',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '1rem',
              width: 'fit-content',
            }}
          >
            ▶ Load Sample Case
          </button>
          <p style={{ fontSize: '0.8rem', color: '#888', margin: '0 0 0.5rem' }}>
            Loads <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>devlogs/two-actor/</code> — or upload your own below
          </p>

          {/* Secondary action: load the synthetic fixture that deliberately
              contains illegal transitions, to demo the violation flagging. */}
          <button
            onClick={handleLoadViolationSample}
            style={{
              display: 'block',
              margin: '0.5rem auto 0.5rem',
              padding: '0.625rem 1.5rem',
              background: '#c62828',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '0.9rem',
              width: 'fit-content',
            }}
          >
            ⚠️ Load Violation Sample
          </button>
          <p style={{ fontSize: '0.8rem', color: '#888', margin: '0 0 0.5rem' }}>
            Loads <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>devlogs/synthetic/</code> — two illegal transitions flagged in red
          </p>

          {/* Three-party case: finder + two vendors. Unverified logs — any
              protocol violations will surface via the red flagging. */}
          <button
            onClick={handleLoadFvv}
            style={{
              display: 'block',
              margin: '0.5rem auto 0.5rem',
              padding: '0.625rem 1.5rem',
              background: '#1565c0',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '0.9rem',
              width: 'fit-content',
            }}
          >
            ▶ Load FVV Case (finder + 2 vendors)
          </button>
          <p style={{ fontSize: '0.8rem', color: '#888', margin: '0 0 0.5rem' }}>
            Loads <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>devlogs/fvv/</code> — unverified 3-party case; violations (if any) flagged in red
          </p>

          <div style={{
            margin: '1rem 0 2rem',
            padding: '2rem',
            border: '2px dashed #0d47a1',
            borderRadius: '4px',
            background: '#f0f7ff',
          }}>
            <input
              type="file"
              accept=".jsonl"
              multiple
              onChange={(e) => handleFileUpload(e.target.files, true)}
              id="log-file-input"
              style={{
                display: 'none',
              }}
            />
            <label
              htmlFor="log-file-input"
              style={{
                display: 'block',
                padding: '1rem 2rem',
                background: '#0d47a1',
                color: 'white',
                borderRadius: '4px',
                cursor: 'pointer',
                textAlign: 'center',
                fontWeight: 'bold',
                fontSize: '1rem',
                margin: '0 auto',
                width: 'fit-content',
              }}
            >
              📁 {uploadCount > 0 ? 'Add More Log Files' : 'Select Log Files'}
            </label>
            <p style={{
              textAlign: 'center',
              marginTop: '1rem',
              fontSize: '0.875rem',
              color: '#666',
              lineHeight: '1.5',
            }}>
              {uploadCount === 0 ? (
                <>
                  <strong>Upload from each folder separately:</strong><br />
                  1. Select file(s) from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>devlogs/two-actor/finder/</code><br />
                  2. Click "Add More" and select from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>vendor/</code><br />
                  3. Click "Add More" and select from <code style={{ background: '#fff', padding: '0.125rem 0.375rem', borderRadius: '3px' }}>case-actor/</code>
                </>
              ) : (
                <>You can add more files from other folders</>
              )}
            </p>

            {uploadCount > 0 && (
              <button
                onClick={handleReset}
                style={{
                  display: 'block',
                  margin: '1rem auto 0',
                  padding: '0.5rem 1rem',
                  background: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                🔄 Start Over
              </button>
            )}
          </div>

          {loading && (
            <p style={{ color: '#0d47a1', fontWeight: 'bold' }}>
              Loading and processing log files...
            </p>
          )}

          {error && (
            <p style={{ color: '#d32f2f', fontWeight: 'bold' }}>
              Error: {error}
            </p>
          )}

          <div style={{ marginTop: '2rem', fontSize: '0.875rem', color: '#666' }}>
            <p><strong>Example logs location:</strong></p>
            <code style={{
              display: 'block',
              background: '#f5f5f5',
              padding: '0.5rem',
              borderRadius: '4px',
              marginTop: '0.5rem',
            }}>
              devlogs/two-actor/*/urn_uuid_*-case-log.jsonl
            </code>
          </div>
        </div>
      </div>
    )
  }

  // Render timeline visualization
  const activeLanes = getActiveLanes(demoState)

  // Collapse-aware vertical layout. Lanes stack in activeLanes order; a collapsed
  // lane occupies LANE_HEIGHT_COLLAPSED instead of LANE_HEIGHT. Node/arrow/lane Y
  // positions all derive from these helpers so they follow collapse state (the
  // old code assumed every lane was a fixed LANE_HEIGHT).
  const laneHeightOf = (participantId: string) =>
    collapsedParticipants.has(participantId) ? LANE_HEIGHT_COLLAPSED : LANE_HEIGHT
  // Top edge of a lane, found by summing the heights of the lanes above it.
  const laneTopByIndex = (laneIndex: number) => {
    let top = 0
    for (const p of activeLanes) {
      if (p.laneIndex >= laneIndex) continue
      top += laneHeightOf(p.id)
    }
    return top
  }
  // Vertical center of a lane (where nodes/arrows sit) by its lane index.
  const laneCenterByIndex = (laneIndex: number) => {
    const p = activeLanes.find(l => l.laneIndex === laneIndex)
    const h = p ? laneHeightOf(p.id) : LANE_HEIGHT
    return laneTopByIndex(laneIndex) + h / 2
  }
  const isLaneIndexCollapsed = (laneIndex: number) => {
    const p = activeLanes.find(l => l.laneIndex === laneIndex)
    return p ? collapsedParticipants.has(p.id) : false
  }
  const totalHeight = activeLanes.reduce((sum, p) => sum + laneHeightOf(p.id), 0)
  // Content width must cover the rightmost node so the container becomes
  // horizontally scrollable (mirrors App-multivendor). A static width:'100%' +
  // minWidth clamps to the viewport, clipping nodes past it with no scroll.
  const contentWidth = Math.max(1200, demoState.nextXPosition + 500)
  // Lane background = a paler version of that participant's label color (the
  // ActorPanel background). Blend the color toward white so the lane reads as a
  // faint tint of its label rather than the old white/gray alternation.
  const palerTint = (hex: string, towardWhite = 0.6): string => {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
    if (!m) return hex
    const int = parseInt(m[1], 16)
    const r = (int >> 16) & 0xff
    const g = (int >> 8) & 0xff
    const b = int & 0xff
    const mix = (c: number) => Math.round(c + (255 - c) * towardWhite)
    return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Full-width header spanning the sidebar + timeline. It sits ABOVE the
          body row so the dark bar covers the whole page and the swimlanes below
          it start at the same y as the sidebar's actor panels (keeps lanes and
          their labels aligned — previously the header only covered the timeline,
          pushing lanes 80px below the panels). */}
      <div style={{
        flexShrink: 0,
        background: '#2d2d2d',
        borderBottom: '2px solid #0d47a1',
        display: 'flex',
        flexDirection: 'column',
        padding: '0.5rem 1rem',
        gap: '0.5rem',
        zIndex: 5,
      }}>
        {/* Top row - title and file controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <h3 style={{ margin: 0, color: 'white', fontSize: '1.125rem' }}>
            Case Timeline ({demoState.timelineEvents.length} events)
          </h3>
          <div style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}>
            <span style={{
              color: '#4caf50',
              fontSize: '0.875rem',
              background: 'rgba(76, 175, 80, 0.1)',
              padding: '0.25rem 0.75rem',
              borderRadius: '4px',
            }}>
              ✓ {accumulatedEntries.length} entries from {uploadCount} upload(s)
            </span>
            <input
              type="file"
              accept=".jsonl"
              multiple
              onChange={(e) => handleFileUpload(e.target.files, true)}
              id="add-more-files"
              style={{ display: 'none' }}
            />
            <label
              htmlFor="add-more-files"
              style={{
                padding: '0.5rem 1rem',
                background: '#4caf50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 'bold',
              }}
            >
              📁 Add More Files
            </label>
            <button
              onClick={handleReset}
              style={{
                padding: '0.5rem 1rem',
                background: '#f44336',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              🔄 Start Over
            </button>
          </div>
        </div>

        {/* Bottom row - playback controls */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.25rem',
          background: '#e3f2fd',
          borderRadius: '4px',
        }}>
          <button
            onClick={handleRewind}
            disabled={currentEventIndex === 0}
            style={{
              padding: '0.375rem 0.75rem',
              background: currentEventIndex === 0 ? '#555' : '#0d47a1',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentEventIndex === 0 ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
            }}
            title="Rewind to start"
          >
            ⏮
          </button>
          <button
            onClick={handleStepBackward}
            disabled={currentEventIndex === 0}
            style={{
              padding: '0.375rem 0.75rem',
              background: currentEventIndex === 0 ? '#555' : '#0d47a1',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentEventIndex === 0 ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
            }}
            title="Previous event"
          >
            ⏪
          </button>
          <button
            onClick={isPlaying ? handlePause : handlePlay}
            style={{
              padding: '0.375rem 1rem',
              background: '#4caf50',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: 'bold',
            }}
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
          <button
            onClick={handleStepForward}
            disabled={currentEventIndex >= demoState.timelineEvents.length - 1}
            style={{
              padding: '0.375rem 0.75rem',
              background: currentEventIndex >= demoState.timelineEvents.length - 1 ? '#555' : '#0d47a1',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentEventIndex >= demoState.timelineEvents.length - 1 ? 'not-allowed' : 'pointer',
              fontSize: '0.875rem',
            }}
            title="Next event"
          >
            ⏩
          </button>
          <span style={{
            color: '#0d47a1',
            fontWeight: 'bold',
            fontSize: '0.875rem',
            marginLeft: '0.5rem',
          }}>
            Event {currentEventIndex + 1} of {demoState.timelineEvents.length}
          </span>
        </div>
      </div>

      {/* Body row: sidebar + timeline share the same top edge (just below the header). */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
      {/* Left sidebar with actor panels */}
      <div
        ref={sidebarScrollRef}
        onScroll={handleSidebarScroll}
        style={{
          width: `${ACTOR_PANEL_WIDTH}px`,
          background: '#f5f5f5',
          overflowY: 'auto',
          overflowX: 'hidden',
          position: 'relative',
          zIndex: 10,
          boxShadow: '2px 0 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
          {activeLanes.map((participant) => (
            <ActorPanel
              key={participant.id}
              participantId={participant.id}
              name={participant.name}
              role={participant.role}
              color={participant.color}
              rmState={participant.rmState}
              emState={demoState.emState}
              vfdState={participant.vfdState}
              pxaState={demoState.pxaState}
              actions={[]} // No actions in replay mode
              onActionClick={() => {}}
              isCollapsed={collapsedParticipants.has(participant.id)}
              onToggleCollapse={() => toggleParticipantCollapse(participant.id)}
            />
          ))}
        </div>
      </div>

      {/* Main timeline area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Scrollable timeline */}
        <div
          ref={timelineScrollRef}
          onScroll={handleTimelineScroll}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: eventLogCollapsed ? '40px' : '200px',
            overflowY: 'auto',
            overflowX: 'auto',
            background: '#fafafa',
          }}
        >
          <div style={{
            height: `${totalHeight}px`,
            width: `${contentWidth}px`,
            position: 'relative',
          }}>
            {/* Lane backgrounds */}
            {activeLanes.map((participant) => (
              <div
                key={`lane-${participant.id}`}
                style={{
                  position: 'absolute',
                  top: laneTopByIndex(participant.laneIndex),
                  left: 0,
                  right: 0,
                  height: laneHeightOf(participant.id),
                  borderBottom: '1px solid #ddd',
                  background: palerTint(participant.color),
                }}
              />
            ))}

            {/* SVG layer for timeline events. No pointerEvents:'none' here — that
                would block node hover (the nodes live inside this SVG and rely on
                mouse events reaching their rects). Non-interactive elements
                (arrows, violation outline) opt out individually instead. */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: `${contentWidth}px`,
                height: '100%',
              }}
            >
              {/* Arrow markers. `arrowhead` is the fixed gray head for horizontal
                  in-lane arrows. `arrowhead-ctx` uses fill="context-stroke" so the
                  head automatically matches its line's stroke color — this lets
                  vertical consequence arrows carry ANY vendor's color without a
                  per-color marker (supports N vendors). */}
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="16"
                  markerHeight="10"
                  refX="16"
                  refY="5"
                  orient="auto"
                >
                  <polygon points="0 0, 16 5, 0 10" fill="#666" />
                </marker>
                <marker
                  id="arrowhead-ctx"
                  markerWidth="16"
                  markerHeight="10"
                  refX="16"
                  refY="5"
                  orient="auto"
                >
                  <polygon points="0 0, 16 5, 0 10" fill="context-stroke" />
                </marker>
              </defs>

              {/* Draw arrows from decision to consequence nodes */}
              {demoState.timelineEvents.slice(0, currentEventIndex + 1).map((event) => {
                if (event.causedBy) {
                  const causeEvent = demoState.timelineEvents.find((e) => e.id === event.causedBy)
                  if (causeEvent) {
                    const allParticipants = Array.from(demoState.participants.values())
                    const y1 = laneCenterByIndex(causeEvent.lane)
                    const y2 = laneCenterByIndex(event.lane)

                    // Use the collapsed NODE height (not lane height) so the arrow
                    // meets the smaller node exactly, mirroring App-multivendor.
                    const sourceCollapsed = isLaneIndexCollapsed(causeEvent.lane)
                    const targetCollapsed = isLaneIndexCollapsed(event.lane)
                    const sourceRectHalfHeight = (sourceCollapsed ? NODE_HEIGHT_COLLAPSED : NODE_HEIGHT) / 2
                    const targetRectHalfHeight = (targetCollapsed ? NODE_HEIGHT_COLLAPSED : NODE_HEIGHT) / 2

                    const direction = y2 > y1 ? 1 : -1
                    const adjustedY1 = y1 + (sourceRectHalfHeight * direction)
                    const adjustedY2 = y2 - (targetRectHalfHeight * direction)

                    // Arrow color = the target participant's consequence color
                    // (works for any vendor-N via nodeColorsFor). The context-stroke
                    // marker inherits this color. No arrowhead when the target lane
                    // is collapsed (matches multivendor).
                    const targetParticipant = allParticipants.find(p => p.laneIndex === event.lane)
                    const arrowColor = targetParticipant
                      ? nodeColorsFor(targetParticipant.id).consequence
                      : '#999'
                    const arrowMarker = targetParticipant && !targetCollapsed ? 'url(#arrowhead-ctx)' : ''

                    // Thinner, tighter-dashed line when pointing at a collapsed lane.
                    const strokeWidth = targetCollapsed ? 1.5 : 3
                    const strokeDasharray = targetCollapsed ? '3,3' : '6,6'

                    return (
                      <line
                        key={`edge-${event.id}`}
                        x1={causeEvent.x}
                        y1={adjustedY1}
                        x2={event.x}
                        y2={adjustedY2}
                        stroke={arrowColor}
                        strokeWidth={strokeWidth}
                        strokeDasharray={strokeDasharray}
                        markerEnd={arrowMarker}
                      />
                    )
                  }
                }
                return null
              })}

              {/* Horizontal flow arrows: a black arrow points into each decision
                  node from the previous node in its OWN lane (matches the other
                  demos). Only enabling relationships get an arrow:
                  consequence→decision and decision→decision; a decision→consequence
                  link is already shown by the vertical (causedBy) arrow. Restricted
                  to the visible slice so playback reveals arrows step by step. */}
              {demoState.timelineEvents.slice(0, currentEventIndex + 1).map((event, idx, visible) => {
                const nextInLane = visible.find(
                  (e, i) => i > idx && e.lane === event.lane && e.x !== event.x
                )
                if (!nextInLane) return null

                const shouldDrawArrow =
                  (event.type === 'consequence' && nextInLane.type === 'decision') ||
                  (event.type === 'decision' && nextInLane.type === 'decision')
                if (!shouldDrawArrow) return null

                const y = laneCenterByIndex(event.lane)
                const collapsed = isLaneIndexCollapsed(event.lane)
                // Nodes keep full width when collapsed (collapse is vertical only).
                const halfW = NODE_WIDTH / 2
                const startX = event.x + halfW // edge of this node
                const endX = nextInLane.x - halfW // edge of next node
                // Keep the arrowhead on horizontal arrows even when collapsed;
                // only thin the stroke (matches App-multivendor).
                const strokeWidth = collapsed ? 1.5 : 3

                return (
                  <line
                    key={`arrow-horizontal-${event.id}`}
                    x1={startX}
                    y1={y}
                    x2={endX}
                    y2={y}
                    stroke="#666"
                    strokeWidth={strokeWidth}
                    markerEnd="url(#arrowhead)"
                  />
                )
              })}

              {/* Draw timeline event nodes */}
              {demoState.timelineEvents.slice(0, currentEventIndex + 1).map((event) => {
              const participant = demoState.participants.get(event.participantId || event.actor)
              if (!participant) return null

              // Get the appropriate colors for this participant (any vendor-N).
              const pid = event.participantId || event.actor
              const participantColors = nodeColorsFor(pid)

              const fillColor = event.type === 'decision'
                ? (hoveredEvent === event.id ? participantColors.decisionHover : participantColors.decision)
                : (hoveredEvent === event.id ? participantColors.consequenceHover : participantColors.consequence)

              // Center the node on the lane (matches the arrow endpoint math,
              // which targets lane center). Uses collapse-aware lane centers so
              // nodes follow their lane when it collapses.
              const yPosition = laneCenterByIndex(event.lane)
              const laneCollapsed = isLaneIndexCollapsed(event.lane)
              // Match AnimatedNode's dimensions for the violation outline: full
              // width always (collapse is vertical only), collapsed height when collapsed.
              const outlineW = NODE_WIDTH
              const outlineH = laneCollapsed ? NODE_HEIGHT_COLLAPSED : NODE_HEIGHT

              return (
                <g key={event.id}>
                  <AnimatedNode
                    event={event}
                    allEvents={demoState.timelineEvents}
                    isHovered={hoveredEvent === event.id}
                    fillColor={fillColor}
                    yPosition={yPosition}
                    getCauseEventY={(eventId) => {
                      const causeEvent = demoState.timelineEvents.find((e) => e.id === eventId)
                      return causeEvent ? laneCenterByIndex(causeEvent.lane) : 0
                    }}
                    animateOnMount
                    isCollapsed={laneCollapsed}
                    onMouseEnter={() => setHoveredEvent(event.id)}
                    onMouseLeave={() => setHoveredEvent(null)}
                  />
                  {/* Protocol-violation outline: the derived trigger was illegal
                      from the shadow state at this point (see caseLedgerMapper).
                      AnimatedNode centers its rect on yPosition, so match that. */}
                  {event.violation && (
                    <>
                      <rect
                        x={event.x - outlineW / 2 - 3}
                        y={yPosition - outlineH / 2 - 3}
                        width={outlineW + 6}
                        height={outlineH + 6}
                        rx="10"
                        ry="10"
                        fill="none"
                        stroke="#d32f2f"
                        strokeWidth={4}
                        pointerEvents="none"
                      />
                      <text
                        x={event.x + outlineW / 2 - 6}
                        y={yPosition - outlineH / 2 + 4}
                        textAnchor="end"
                        fontSize="22"
                        pointerEvents="none"
                      >
                        ⚠️
                      </text>
                    </>
                  )}
                  {/* Inferred-step annotation (tripwire): the mapper bridged this
                      node's state diff with a multi-hop path because intermediate
                      states weren't logged — so this step was inferred, not observed.
                      Distinct from a violation: amber dashed outline + ℹ️, not red.
                      Suppressed when the node is already a violation. */}
                  {event.inferred && !event.violation && (
                    <>
                      <rect
                        x={event.x - outlineW / 2 - 3}
                        y={yPosition - outlineH / 2 - 3}
                        width={outlineW + 6}
                        height={outlineH + 6}
                        rx="10"
                        ry="10"
                        fill="none"
                        stroke="#f9a825"
                        strokeWidth={3}
                        strokeDasharray="5,4"
                        pointerEvents="none"
                      />
                      <text
                        x={event.x + outlineW / 2 - 6}
                        y={yPosition - outlineH / 2 + 4}
                        textAnchor="end"
                        fontSize="20"
                        pointerEvents="none"
                      >
                        ℹ️
                      </text>
                    </>
                  )}
                </g>
              )
              })}
            </svg>

            {/* Hover tooltip: node label + detail bullets, and — for flagged
                nodes — an explanation of WHY the transition is illegal per the
                protocol. Positioned in the same coordinate space as the nodes. */}
            {hoveredEvent && (() => {
              const event = demoState.timelineEvents.find((e) => e.id === hoveredEvent)
              if (!event) return null
              const y = laneCenterByIndex(event.lane)
              return (
                <div
                  style={{
                    position: 'absolute',
                    top: y + 60,
                    left: event.x - 140,
                    background: 'white',
                    border: `2px solid ${event.violation ? '#d32f2f' : event.inferred ? '#f9a825' : '#333'}`,
                    borderRadius: '8px',
                    padding: '0.75rem',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.15)',
                    zIndex: 1000,
                    width: '280px',
                    pointerEvents: 'none',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>
                    {event.violation ? '⚠️ ' : event.inferred ? 'ℹ️ ' : ''}{event.label}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#666' }}>
                    {event.consequences.map((c, i) => (
                      <div key={i} style={{ marginBottom: '0.25rem' }}>• {c}</div>
                    ))}
                  </div>
                  {event.violation && event.violationReason && (
                    <div style={{
                      marginTop: '0.5rem',
                      paddingTop: '0.5rem',
                      borderTop: '1px solid #eee',
                      fontSize: '0.75rem',
                      color: '#c62828',
                    }}>
                      <strong>Protocol violation:</strong> {event.violationReason}
                    </div>
                  )}
                  {!event.violation && event.inferred && event.inferredNote && (
                    <div style={{
                      marginTop: '0.5rem',
                      paddingTop: '0.5rem',
                      borderTop: '1px solid #eee',
                      fontSize: '0.75rem',
                      color: '#e65100',
                    }}>
                      <strong>Inferred step:</strong> {event.inferredNote}
                    </div>
                  )}
                </div>
              )
            })()}
          </div>
        </div>

        {/* Event log panel */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: eventLogCollapsed ? '40px' : '200px',
          background: '#2d2d2d',
          borderTop: '2px solid #0d47a1',
          transition: 'height 0.3s ease',
        }}>
          <div
            onClick={() => setEventLogCollapsed(!eventLogCollapsed)}
            style={{
              height: '40px',
              display: 'flex',
              alignItems: 'center',
              padding: '0 1rem',
              cursor: 'pointer',
              background: '#0d47a1',
              color: 'white',
              fontWeight: 'bold',
            }}
          >
            <span>Event Log ({demoState.eventLog.length} entries)</span>
            <span style={{ marginLeft: 'auto' }}>
              {eventLogCollapsed ? '▲' : '▼'}
            </span>
          </div>

          {!eventLogCollapsed && (
            <div style={{
              height: '160px',
              overflowY: 'auto',
              padding: '0.5rem 1rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#ddd',
            }}>
              {demoState.eventLog.map((log, idx) => (
                <div key={idx} style={{ marginBottom: '0.25rem' }}>
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}

export default AppLogReplay
