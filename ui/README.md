# Vultron UI Demo

Interactive visualization demonstrating the Vultron Coordinated Vulnerability Disclosure (CVD) protocol with both single-vendor and multi-vendor scenarios.

## Prerequisites

- Node.js (with npm)

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Run the development server:**
   ```bash
   npm run dev
   ```

3. **View the demo:**
   Open your browser to the URL shown in the terminal (usually `http://localhost:5173`)

## Demo Modes

The application includes **two interactive demos** that you can toggle between:

### Single-Vendor Demo (Original)
- **Participants:** Finder, Vendor, CaseActor
- **Purpose:** Demonstrates the basic CVD workflow with one vendor
- **Key Features:**
  - Report Management (RM) state machine
  - Vendor Fix Development (VFD) state machine
  - Embargo Management (EM) state machine
  - Public/eXploit/Attacks (PXA) tracking

### Multi-Vendor Demo
- **Participants:** Finder, up to 2 additional vendors (dynamic), CaseActor
- **Purpose:** Shows how multiple vendors can independently participate in the same vulnerability case
- **Key Features:**
  - **Independent vendor states:** Each vendor tracks their own RM/VFD progression
  - **Shared case state:** All participants see the same EM and PXA states
  - **Dynamic vendor invitations:** Finder can invite additional vendors mid-case
  - **Vendor-specific replies:** Each vendor can independently respond to questions
  - **Individual closure:** Vendors can close their participation independently

### Toggling Between Demos

Use the demo selector at the top of the page:
- Click "**Single-Vendor Demo**" to view the original single-vendor workflow
- Click "**Multi-Vendor Demo**" to view the multi-vendor coordination scenario

> **Note:** Switching demos resets all state, so any progress in the current demo will be lost.

## Available Commands

- `npm run dev` - Start the development server with hot reload
- `npm run build` - Build for production
- `npm run preview` - Preview the production build locally
- `npm run lint` - Run ESLint

## Understanding the Visualization

### Node Types
- **Decision Nodes (dark colors):** User actions that require participant input
- **Consequence Nodes (light colors):** Automatic system responses to decisions

### Participant Lanes
Each participant has their own horizontal lane showing:
- Their available actions (decision nodes)
- Automated consequences in their context
- Their current state across all relevant state machines

### State Machines

The demo accurately represents the Vultron protocol state machines:

1. **RM (Report Management)** - Participant-specific
   - Tracks: `START` → `RECEIVED` → `VALID` → `ACCEPTED` → `CLOSED`
   - Each participant maintains their own RM state

2. **VFD (Vendor Fix Development)** - Vendor-specific
   - Tracks: `vfd` → `Vfd` → `VFd` → `VFD`
   - Only vendors track VFD state
   - Independent of embargo negotiations

3. **EM (Embargo Management)** - Case-wide
   - Shared across all participants
   - Tracks embargo proposals and agreements

4. **PXA (Public/eXploit/Attacks)** - Case-wide
   - Tracks public awareness, exploit publication, and active attacks
   - Displayed by CaseActor only
   - Key rule: Exploit (X) automatically implies Public (P)

### UI Features

- **Collapsible Event Log:** Bottom panel showing chronological event history
- **Synchronized Scrolling:** Sidebar and timeline scroll together vertically
- **External Events:** Buttons to simulate exploit publication (⚠️) and attacks (🔥)
- **State Indicators:** Each participant displays their current state machine values

## Tech Stack

- React 19 + TypeScript
- Vite (build tool)
- [@xyflow/react](https://reactflow.dev/) - Interactive node-based visualization library

## Architecture

### Key Files
- [src/main.tsx](src/main.tsx) - Demo selector entry point
- [src/DemoSelector.tsx](src/DemoSelector.tsx) - Toggle component
- [src/App-multivendor.tsx](src/App-multivendor.tsx) - Multi-vendor demo (~750 lines)
- [src/App.tsx](src/App.tsx) - Original single-vendor demo
- [src/actions/](src/actions/) - Pure function action handlers
- [src/state/](src/state/) - State management helpers

### Design Patterns
- **Pure Functions:** All action handlers are immutable
- **Participant-Based State:** `Map<string, ParticipantState>` for independent tracking
- **Dynamic Lane Management:** Lane indices update as vendors join
- **Consequence Propagation:** Actions create consequences in all relevant participants' lanes

## Reference

For detailed protocol documentation, see:
- [Case State Model](../notes/case-state-model.md)
- [State Machine Definitions](../vultron/core/states/)
- [Model Interactions](../docs/topics/process_models/model_interactions/)
