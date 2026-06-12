# Multi-Folder Log Upload - How It Works

## The Problem

When running the container-based demos, log files are generated in **separate subfolders**:

```
devlogs/two-actor/
├── finder/
│   └── urn_uuid_...-case-log.jsonl
├── vendor/
│   └── urn_uuid_...-case-log.jsonl
└── case-actor/
    └── urn_uuid_...-case-log.jsonl
```

Browser file pickers **only let you select files from one folder at a time**, so you can't Ctrl+click files across different folders.

## The Solution: Sequential Upload with Accumulation

The Log Replay demo now supports **adding files from multiple uploads**:

### Step-by-Step Process

1. **First Upload**: Click "📁 Select Log Files"
   - Navigate to `devlogs/two-actor/finder/`
   - Select the JSONL file
   - Click "Open"
   - ✅ Status shows: "Loaded X log entries from 1 upload(s)"

2. **Second Upload**: Click "📁 Add More Log Files"
   - Navigate to `devlogs/two-actor/vendor/`
   - Select the JSONL file
   - Click "Open"
   - ✅ Status shows: "Loaded X log entries from 2 upload(s)"

3. **Third Upload**: Click "📁 Add More Log Files"
   - Navigate to `devlogs/two-actor/case-actor/`
   - Select the JSONL file
   - Click "Open"
   - ✅ Status shows: "Loaded X log entries from 3 upload(s) • Y events visualized"

4. **View Timeline**: After all uploads, the complete timeline appears with all participants

### Key Features

- **Accumulation**: Each upload adds to the previous ones (doesn't replace them)
- **Live Update**: Timeline rebuilds after each upload, showing progress
- **Status Display**: Always shows how many entries and events are loaded
- **Start Over**: "🔄 Start Over" button clears everything to begin fresh

## How It Works Internally

```typescript
// State tracks accumulated entries
const [accumulatedEntries, setAccumulatedEntries] = useState<CaseLogEntry[]>([])
const [uploadCount, setUploadCount] = useState(0)

// handleFileUpload accumulates entries
const allEntries = shouldAccumulate 
  ? [...accumulatedEntries, ...newEntries]  // Add to existing
  : newEntries                               // Replace (not used for now)

// Merge and sort by timestamp
const mergedEntries = mergeLogEntries(allEntries)

// Build timeline
const state = buildTimelineFromLogs(mergedEntries)
```

### Merge and Sort Logic

The `mergeLogEntries()` function in [jsonlParser.ts](src/utils/jsonlParser.ts) sorts all entries by their `receivedAt` timestamp, ensuring chronological order regardless of upload sequence.

```typescript
export function mergeLogEntries(entries: CaseLogEntry[]): CaseLogEntry[] {
  return entries.sort((a, b) => {
    const timeA = new Date(a.receivedAt).getTime()
    const timeB = new Date(b.receivedAt).getTime()
    return timeA - timeB
  })
}
```

This means you can upload files in **any order** and the timeline will still be correct!

## Alternative Workarounds

If you want to avoid multiple uploads:

### Option 1: Copy Files to Single Folder

```bash
# Create a temporary folder
mkdir -p /tmp/vultron-logs

# Copy all JSONL files to one place
cp devlogs/two-actor/finder/*.jsonl /tmp/vultron-logs/
cp devlogs/two-actor/vendor/*.jsonl /tmp/vultron-logs/
cp devlogs/two-actor/case-actor/*.jsonl /tmp/vultron-logs/

# Now you can select all three files in one upload from /tmp/vultron-logs/
```

### Option 2: Symlinks (Unix/Mac/Linux)

```bash
# Create a folder with symlinks
mkdir -p /tmp/vultron-logs-symlinked
ln -s $(pwd)/devlogs/two-actor/finder/*.jsonl /tmp/vultron-logs-symlinked/
ln -s $(pwd)/devlogs/two-actor/vendor/*.jsonl /tmp/vultron-logs-symlinked/
ln -s $(pwd)/devlogs/two-actor/case-actor/*.jsonl /tmp/vultron-logs-symlinked/

# Upload all from the symlinked folder
```

### Option 3: Future Enhancement - Auto-Load Button

We could add a "Load Two-Actor Demo" button that:
- Automatically fetches logs from a known URL path
- Requires dev server to serve the `devlogs/` folder
- Would look something like:

```typescript
// Future feature (not yet implemented)
const handleLoadDemoLogs = async () => {
  const paths = [
    '/devlogs/two-actor/finder/urn_uuid_...',
    '/devlogs/two-actor/vendor/urn_uuid_...',
    '/devlogs/two-actor/case-actor/urn_uuid_...',
  ]
  // Fetch and load automatically
}
```

This would require:
1. Vite config to serve `devlogs/` folder
2. Way to discover the case ID (maybe a manifest file)
3. Button in the UI

## User Experience Flow

```
┌─────────────────────────────────────────┐
│  Log Replay Demo - No Files Loaded      │
│                                          │
│  📁 Select Log Files                    │
│  Instructions: Upload from each folder  │
└─────────────────────────────────────────┘
                    ↓ (User uploads finder log)
┌─────────────────────────────────────────┐
│  ✓ Loaded 14 entries from 1 upload(s)  │
│                                          │
│  📁 Add More Log Files                  │
│  🔄 Start Over                          │
└─────────────────────────────────────────┘
                    ↓ (User uploads vendor log)
┌─────────────────────────────────────────┐
│  ✓ Loaded 28 entries from 2 upload(s)  │
│                                          │
│  📁 Add More Log Files                  │
│  🔄 Start Over                          │
└─────────────────────────────────────────┘
                    ↓ (User uploads case-actor log)
┌─────────────────────────────────────────┐
│  ✓ Loaded 42 entries from 3 upload(s)  │
│     • 15 events visualized               │
│                                          │
│  [Full Timeline Visualization Appears]  │
└─────────────────────────────────────────┘
```

## Implementation Files

- [App-logreplay.tsx](src/App-logreplay.tsx) - Main component with accumulation logic
- [jsonlParser.ts](src/utils/jsonlParser.ts) - `mergeLogEntries()` function
- [logEventMapper.ts](src/utils/logEventMapper.ts) - Timeline builder

All changes are non-breaking and the sequential upload pattern is now the primary UX.
