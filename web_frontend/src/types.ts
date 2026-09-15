<<<<<<< HEAD
=======
// TypeScript definitions for JARVIS Organism Console & Cognitive OS

export type AppTheme = 'dark' | 'light';
export type UserRole = 'admin' | 'guest';
export type ConsoleView = 'home' | 'dashboard' | 'cli' | 'inspector' | 'user_chat' | 'codebox' | 'call';

export type PipelineStage = 'IDLE' | 'PERCEIVING' | 'INDEXING' | 'EXECUTING';

export interface StageTransition {
  stage: PipelineStage;
  previous_stage: PipelineStage;
  timestamp: number;
  duration_in_previous: number;
  detail?: Record<string, any>;
}

export interface ExtractionAttempt {
  stage: 'primary' | 'refined' | 'safe_fallback';
  ok: boolean;
  reason: string | null;
  timestamp: number;
}

export interface ExtractionItem {
  schema: string;
  stage_used: 'primary' | 'refined' | 'safe_fallback';
  fallback_active: boolean;
  attempts: ExtractionAttempt[];
  timestamp: number;
}

export interface LearningQueueState {
  active: boolean;
  alive: boolean;
  pending: number;
  processed: number;
  failed: number;
  dropped: number;
}

export interface LogEntry {
  tag: string;
  message: string;
  level: 'warning' | 'error' | 'info' | 'debug';
  timestamp: number;
}

export interface LiveStateResponse {
  version: number;
  pid: number;
  updated_at: number;
  runtime: 'ONLINE' | 'OFFLINE';
  stage: PipelineStage;
  stage_detail: Record<string, any>;
  stage_since: number;
  fallback_active: boolean;
  pipeline_trace: StageTransition[];
  extractions: ExtractionItem[];
  learning: LearningQueueState;
  logs: LogEntry[];
  organs: Record<string, { type: string; attached: boolean }>;
  heartbeat: { running: boolean; beats: number; idle: boolean };
  llm_ready: boolean;
}

export interface ContractValidationEntry {
  schema: string;
  status: 'PASS' | 'FAIL';
  error?: string;
  timestamp: number;
}

export interface TurnTrace {
  turn_id?: string;
  source: string;
  query: string;
  response_preview: string;
  perception: {
    // Real field names from core/orchestration/blueprint_brain.py's
    // _perceive(). normalized_input/basic_intent are kept as optional
    // legacy aliases only -- the real pipeline writes normalized_text
    // and intent.
    normalized_text?: string;
    normalized_input?: string;
    language: string;
    confidence: number;
    intent?: Record<string, any>;
    basic_intent?: Record<string, any>;
    // Real entities are objects ({text, type, entity_id}), not plain
    // strings -- see core/cognition/semantic_understanding/
    // bridge_to_cognition.py's understand(). Never render one directly
    // as a React child; use entityLabel()/display() first.
    entities: Array<string | { text: string; type?: string; entity_id?: string }>;
    metadata?: {
      source: string;
      uncertainty: number;
      goal: string | null;
      reason: string;
    };
    // The full real semantic_understanding contract output lives here,
    // nested under perception -- NOT at the top level of TurnTrace.
    semantic_understanding?: {
      normalized_text: string;
      intent: Record<string, any>;
      entities: any[];
      relations: any[];
      events: any[];
      references: any[];
      confidence: number;
      // Object, not a string -- {source, degraded?, reason?}.
      provenance: { source: string; degraded?: boolean; reason?: string } | string;
      inferences: any[];
      unknowns: any[];
    };
    semantic_evidence?: Record<string, any>;
  };
  cognitive_route: {
    mode: string;
    confidence: number;
    fallback_allowed: boolean;
    evidence: Array<[string, any]>;
  };
  brain_decision: {
    mode: string;
    status: string;
    skill?: string;
    goal?: string;
    error?: string;
  };
  action_response: {
    mode: string;
    status: string;
    response: string;
    action_payload?: any;
    error?: string;
  };
  llm_available: boolean;
  pipeline_success: boolean;
  timings: {
    total: number;
    [stage: string]: number;
  };
  contract_validation_trace: ContractValidationEntry[];
  llm_budget: {
    active: boolean;
    calls: number;
    max_calls: number;
    reserved_output_tokens: number;
    max_output_tokens: number;
  };
  // Real supplementary data attached server-side by backend/trace_utils.py's
  // real_turn_trace() (from brain.last_context / brain.status()) -- the raw
  // trace object itself never carries these.
  indexing?: { memory: number; knowledge: number; graph: number };
  learning_queue?: { alive: boolean; pending: number; processed: number; failed: number; dropped: number; active: boolean };
}

export interface BackendStatusResponse {
  status: 'success' | 'error';
  organs: Record<string, { type: string; attached: boolean }>;
  heartbeat: { running: boolean; beat_count: number; is_idle: boolean };
  brain: {
    async_learning_queue: LearningQueueState;
    [key: string]: any;
  };
  goals?: Record<string, any>;
  scheduler?: Record<string, any>;
  last_turn_trace: TurnTrace;
}

export interface SystemResourcesData {
  timestamp: number;
  /** False when the real backend endpoint was unreachable and every
   *  field below is zeroed rather than real -- added 2026-09-14 so a
   *  down backend cannot look identical to a healthy one. */
  available?: boolean;
  process: {
    max_rss_mb: number;
    user_cpu_seconds: number;
    system_cpu_seconds: number;
    threads: number;
  };
  llm: {
    backend: string;
    ready: boolean;
    local_loaded: boolean;
    last_error: string | null;
    budget: { calls: number; max_calls: number };
  };
  self_evaluation: {
    evaluations: number;
    success_rate: number;
    average_score: number;
    last_evaluated_at: number;
  };
  knowledge: {
    built: number;
    accepted: number;
    rejected: number;
    pending: number;
    last_built_at: number;
  };
  evolution: {
    proposals: number;
    approved: number;
    applied: number;
    rejected: number;
    last_evolution_at: number;
  };
}

// Condensed per-turn trace shown inline in a chat bubble (see
// backend/trace_utils.py's turn_trace_summary()). Every field is
// sourced from the same real brain.last_turn_trace / brain.last_context
// the full TurnTrace/TraceTreeViewer uses -- just condensed for a
// compact widget instead of the full per-stage breakdown.
export interface TraceSummary {
  traceId: string;
  latencySeconds: number;
  mode: string;
  status: string;
  memoryMatches: number;
  knowledgeMatches: number;
  graphRelations: number;
  semanticRelations: Array<{ subject: string; predicate: string; value: any }>;
  llmAvailable: boolean;
  pipelineSuccess: boolean;
}

export interface ActivityHistoryItem {
  turnId: string;
  startTime: number;
  endTime: number | null; // null represents in-progress turn
  durationSeconds: number;
  stagePath: string[];
  query: string;
  responsePreview: string;
  success: boolean;
  trace: TurnTrace;
}

// Chat Models for User and CLI views
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
export interface ChatMessage {
  id: string;
  sessionId: string;
  sender: 'user' | 'jarvis';
  text: string;
  timestamp: string;
  source: 'web' | 'cli' | 'autonomous';
  traceLog?: CognitiveTrace;
  extractedFact?: {
    subject: string;
    predicate: string;
    value: string;
    confidence?: number;
  };
}

export interface CognitiveTrace {
  traceId: string;
  latencySeconds: number;
  memoryLookupSeconds: number;
  llmInferenceSeconds: number;
  vectorMatches: Array<{
    id: string;
    subject: string;
    predicate: string;
    value: string;
    similarity: number;
  }>;
  graphRelations: Array<{
    subject: string;
    predicate: string;
    target: string;
  }>;
  learningPipelineStatus: 'validated' | 'queued' | 'consolidated';
  typosCorrected?: Array<{ raw: string; corrected: string }>;
}

export type AppTheme = 'dark' | 'light';

export interface ChatSession {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  pinned: boolean;
  msgCount: number;
  category: 'Today' | 'Previous';
}

export type SessionItem = ChatSession;

export interface EngramFact {
  id: string;
  subject: string;
  predicate: string;
  value: string;
  confidence: number;
  importance: number;
  evidenceCount: number;
  source: string;
  tags: string[];
  createdAt: number;
  updatedAt: number;
  faissId: number;
  status: 'ACCEPTED' | 'CANDIDATE' | 'REJECTED';
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'subject' | 'value' | 'concept';
  color?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  predicate: string;
  confidence?: number;
}

export interface OrganStatusInfo {
  name: string;
  classType: string;
  isAttached: boolean;
  role: string;
  metrics: string;
  health: 'green' | 'yellow' | 'red';
}

export interface CuriosityGoal {
  id: string;
  text: string;
  priority: number;
  status: 'pending' | 'active' | 'completed';
  origin: 'user' | 'curiosity' | 'self';
  progress: string[];
  createdAt: number;
}

export interface EvolutionProposal {
  id: string;
  target: string;
  reason: string;
  status: 'PROPOSED' | 'VALIDATED' | 'APPROVED' | 'APPLIED' | 'REJECTED';
  score: number;
  createdAt: number;
}

export type ActiveTab = 'chat' | 'matrix' | 'memory' | 'autonomy' | 'code';

export interface OrganismTelemetry {
  pulseState: string;
  beatCount: number;
  bpm: number;
  pulseWave: string;
  runtimeSeconds: number;
  isIdle: boolean;
  activeModel: string;
  ramUsageMB: number;
  totalTokensProcessed: number;
  avgLatencyMs: number;
  organs: OrganStatusInfo[];
}

export interface PythonCodeFile {
  filename: string;
  path: string;
  category: 'core' | 'memory' | 'learning' | 'orchestration' | 'autonomy' | 'backend' | 'config' | 'scripts';
  description: string;
  code: string;
}
