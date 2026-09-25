# Multi-Folder Log Upload - How It Works

## The Problem

When running the container-based demos, log files are generated in **separate subfolders**:

```
devlogs/fv/
├── finder/
│   └── urn_uuid_...-case-ledger.jsonl
├── vendor/
│   └── urn_uuid_...-case-ledger.jsonl
└── case-actor/
    └── urn_uuid_...-case-ledger.jsonl
```

Browser file pickers **only let you select files from one folder at a time**, so you can't Ctrl+click files across different folders.

## The Solution: Sequential Upload with Accumulation

The Log Replay demo now supports **adding files from multiple uploads**:

### Step-by-Step Process

1. **First Upload**: Click "📁 Select Log Files"
   - Navigate to `devlogs/fv/finder/`
   - Select the JSONL file
   - Click "Open"
   - ✅ Status shows: "Loaded X log entries from 1 upload(s)"

2. **Second Upload**: Click "📁 Add More Log Files"
   - Navigate to `devlogs/fv/vendor/`
   - Select the JSONL file
   - Click "Open"
   - ✅ Status shows: "Loaded X log entries from 2 upload(s)"

3. **Third Upload**: Click "📁 Add More Log Files"
   - Navigate to `devlogs/fv/case-actor/`
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
const [accumulatedEntries, setAccumulatedEntries] = useState<CaseLedgerEntry[]>([])
const [uploadCount, setUploadCount] = useState(0)

// handleFileUpload accumulates entries
const allEntries = shouldAccumulate
  ? [...accumulatedEntries, ...newEntries]  // Add to existing
  : newEntries                               // Replace (not used for now)

// Dedup + order, then build the timeline
const ordered = normalizeLedger(allEntries)
const state = buildTimelineFromCaseLedger(ordered)
```

### Merge and Sort Logic

`normalizeLedger()` in [caseLedgerParser.ts](src/utils/caseLedgerParser.ts)
**dedups by `entryHash`** (so uploading overlapping per-actor copies is safe) and
**sorts by `logIndex`** — the authoritative order.

```typescript
export function normalizeLedger(entries: CaseLedgerEntry[]): CaseLedgerEntry[] {
  const byHash = new Map<string, CaseLedgerEntry>()
  for (const e of entries) byHash.set(e.entryHash, e)
  return [...byHash.values()].sort((a, b) => a.logIndex - b.logIndex)
}
```

> **Do not sort by `receivedAt`.** Several entries share a wall-clock second, so a
> timestamp sort would scramble their order — `logIndex` is the source of truth.

Because ordering comes from `logIndex` and duplicates are dropped by `entryHash`,
you can upload files (and per-actor copies) in **any order** and the timeline is
still correct.

## Alternative Workarounds

If you want to avoid multiple uploads:

### Option 1: Copy Files to Single Folder

```bash
# Create a temporary folder
mkdir -p /tmp/vultron-logs

# Copy all JSONL files to one place
cp devlogs/fv/finder/*.jsonl /tmp/vultron-logs/
cp devlogs/fv/vendor/*.jsonl /tmp/vultron-logs/
cp devlogs/fv/case-actor/*.jsonl /tmp/vultron-logs/

# Now you can select all three files in one upload from /tmp/vultron-logs/
```

### Option 2: Symlinks (Unix/Mac/Linux)

```bash
# Create a folder with symlinks
mkdir -p /tmp/vultron-logs-symlinked
ln -s $(pwd)/devlogs/fv/finder/*.jsonl /tmp/vultron-logs-symlinked/
ln -s $(pwd)/devlogs/fv/vendor/*.jsonl /tmp/vultron-logs-symlinked/
ln -s $(pwd)/devlogs/fv/case-actor/*.jsonl /tmp/vultron-logs-symlinked/

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
    '/devlogs/fv/finder/urn_uuid_...',
    '/devlogs/fv/vendor/urn_uuid_...',
    '/devlogs/fv/case-actor/urn_uuid_...',
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
- [caseLedgerParser.ts](src/utils/caseLedgerParser.ts) - `parseCaseLedger()` / `normalizeLedger()`
- [caseLedgerMapper.ts](src/utils/caseLedgerMapper.ts) - `buildTimelineFromCaseLedger()` timeline builder

All changes are non-breaking and the sequential upload pattern is now the primary UX.
