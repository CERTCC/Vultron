import { useState, useCallback } from 'react'
import { ReactFlow, Controls } from '@xyflow/react'
import type { Node, Edge, NodeTypes } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './App.css'
import { Swimlanes } from './components/Swimlanes'
import { ActorNode } from './components/ActorNode'

// Register custom node types
const nodeTypes: NodeTypes = {
  actorNode: ActorNode,
}

// Define swimlane layout (3 horizontal bands)
const LANE_HEIGHT = 250
const swimlanes = [
  {
    id: 'finder',
    label: 'Finder',
    color: '#e3f2fd', // Light blue
    y: 0,
    height: LANE_HEIGHT,
  },
  {
    id: 'vendor',
    label: 'Vendor',
    color: '#f3e5f5', // Light purple
    y: LANE_HEIGHT,
    height: LANE_HEIGHT,
  },
  {
    id: 'caseactor',
    label: 'Case Actor',
    color: '#fff3e0', // Light orange
    y: LANE_HEIGHT * 2,
    height: LANE_HEIGHT,
  },
]

// Define all nodes that will appear during the demo
const allNodes: Node[] = [
  {
    id: 'finder-report',
    type: 'default',
    position: { x: 150, y: LANE_HEIGHT / 2 - 20 },
    data: { label: '📝 Create Report' },
  },
  {
    id: 'vendor-receive',
    type: 'default',
    position: { x: 450, y: LANE_HEIGHT + LANE_HEIGHT / 2 - 20 },
    data: { label: '📥 Receive Report' },
  },
  {
    id: 'vendor-validate',
    type: 'default',
    position: { x: 700, y: LANE_HEIGHT + LANE_HEIGHT / 2 - 20 },
    data: { label: '✅ Validate Report' },
  },
  {
    id: 'vendor-case',
    type: 'default',
    position: { x: 950, y: LANE_HEIGHT + LANE_HEIGHT / 2 - 20 },
    data: { label: '📦 Case Created' },
  },
  {
    id: 'caseactor-participant',
    type: 'default',
    position: { x: 1200, y: LANE_HEIGHT * 2 + LANE_HEIGHT / 2 - 20 },
    data: { label: '🤖 CaseActor (virtual)' },
    style: {
      opacity: 0.6,
      border: '2px dashed #999',
    },
  },
  {
    id: 'finder-replica',
    type: 'default',
    position: { x: 1450, y: LANE_HEIGHT / 2 - 20 },
    data: { label: '📋 Case Replica' },
  },
]

// Define all edges that will appear
const allEdges: Edge[] = [
  {
    id: 'e1',
    source: 'finder-report',
    target: 'vendor-receive',
    animated: true,
    label: 'Offer(Report)',
    type: 'smoothstep',
  },
  {
    id: 'e2',
    source: 'vendor-receive',
    target: 'vendor-validate',
    animated: true,
    label: 'triggers',
    type: 'smoothstep',
  },
  {
    id: 'e3',
    source: 'vendor-validate',
    target: 'vendor-case',
    animated: true,
    label: 'creates',
    type: 'smoothstep',
  },
  {
    id: 'e4',
    source: 'vendor-case',
    target: 'caseactor-participant',
    animated: true,
    label: 'creates participant',
    type: 'smoothstep',
    style: { strokeDasharray: '5,5' },
  },
  {
    id: 'e5',
    source: 'vendor-case',
    target: 'finder-replica',
    animated: true,
    label: 'outbox delivery',
    type: 'smoothstep',
  },
]

// Define demo steps
interface DemoStep {
  title: string
  description: string
  nodeIds: string[]
  edgeIds: string[]
}

const steps: DemoStep[] = [
  {
    title: 'Start',
    description: 'The demo begins with three actors: Finder, Vendor, and CaseActor (virtual).',
    nodeIds: [],
    edgeIds: [],
  },
  {
    title: 'Step 1: Finder Creates Report',
    description: 'The Finder discovers a vulnerability and creates a VulnerabilityReport describing the issue.',
    nodeIds: ['finder-report'],
    edgeIds: [],
  },
  {
    title: 'Step 2: Submit to Vendor',
    description: 'The Finder submits the report to the Vendor\'s inbox as an Offer activity.',
    nodeIds: ['finder-report', 'vendor-receive'],
    edgeIds: ['e1'],
  },
  {
    title: 'Step 3: Vendor Validates Report',
    description: 'The Vendor reviews the report and validates it as legitimate using the ValidateReport trigger.',
    nodeIds: ['finder-report', 'vendor-receive', 'vendor-validate'],
    edgeIds: ['e1', 'e2'],
  },
  {
    title: 'Step 4: Case Automatically Created',
    description: 'Upon validation, a VulnerabilityCase is automatically created with 3 participants and an active embargo (EM.ACTIVE).',
    nodeIds: ['finder-report', 'vendor-receive', 'vendor-validate', 'vendor-case'],
    edgeIds: ['e1', 'e2', 'e3'],
  },
  {
    title: 'Step 5: CaseActor Participant Created',
    description: 'The system automatically creates 3 participants: Vendor, Finder, and CaseActor (virtual). The CaseActor acts as the authoritative ledger.',
    nodeIds: ['finder-report', 'vendor-receive', 'vendor-validate', 'vendor-case', 'caseactor-participant'],
    edgeIds: ['e1', 'e2', 'e3', 'e4'],
  },
  {
    title: 'Step 6: Finder Receives Case Replica',
    description: 'The Vendor\'s outbox automatically delivers a case replica to the Finder. ✓ M1 Complete: Case is active with 3 participants, EM.ACTIVE, and both actors have synchronized case state.',
    nodeIds: ['finder-report', 'vendor-receive', 'vendor-validate', 'vendor-case', 'caseactor-participant', 'finder-replica'],
    edgeIds: ['e1', 'e2', 'e3', 'e4', 'e5'],
  },
]

function App() {
  const [currentStep, setCurrentStep] = useState(0)

  const visibleNodes = allNodes.filter((node) =>
    steps[currentStep].nodeIds.includes(node.id)
  )
  const visibleEdges = allEdges.filter((edge) =>
    steps[currentStep].edgeIds.includes(edge.id)
  )

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleReset = () => {
    setCurrentStep(0)
  }

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <div style={{ padding: '1rem', background: '#f5f5f5', borderBottom: '1px solid #ddd' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#666' }}>
          Vultron Demo (M1: Case Activation)
        </h1>
        <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#666' }}>
          CERT/CC — Research Prototype
        </p>
      </div>

      <div style={{ width: '100%', height: 'calc(100vh - 200px)', position: 'relative' }}>
        <ReactFlow nodes={visibleNodes} edges={visibleEdges} fitView>
          <Swimlanes lanes={swimlanes} />
          <Controls />
        </ReactFlow>
      </div>

      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: '120px',
          background: '#fff',
          borderTop: '2px solid #ddd',
          padding: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>
              {steps[currentStep].title}
            </h3>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#666' }}>
              {steps[currentStep].description}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleReset}
              disabled={currentStep === 0}
              style={{
                padding: '0.5rem 1rem',
                fontSize: '0.9rem',
                cursor: currentStep === 0 ? 'not-allowed' : 'pointer',
                opacity: currentStep === 0 ? 0.5 : 1,
              }}
            >
              Reset
            </button>
            <button
              onClick={handlePrevious}
              disabled={currentStep === 0}
              style={{
                padding: '0.5rem 1rem',
                fontSize: '0.9rem',
                cursor: currentStep === 0 ? 'not-allowed' : 'pointer',
                opacity: currentStep === 0 ? 0.5 : 1,
              }}
            >
              ← Previous
            </button>
            <button
              onClick={handleNext}
              disabled={currentStep === steps.length - 1}
              style={{
                padding: '0.5rem 1.5rem',
                fontSize: '0.9rem',
                fontWeight: 'bold',
                cursor: currentStep === steps.length - 1 ? 'not-allowed' : 'pointer',
                opacity: currentStep === steps.length - 1 ? 0.5 : 1,
                background: currentStep === steps.length - 1 ? '#ccc' : '#4CAF50',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
              }}
            >
              {currentStep === steps.length - 1 ? 'Complete ✓' : 'Next →'}
            </button>
          </div>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#999' }}>
          Step {currentStep + 1} of {steps.length}
        </div>
      </div>
    </div>
  )
}

export default App
