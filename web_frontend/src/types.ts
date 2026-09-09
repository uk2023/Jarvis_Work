// TypeScript definitions for JARVIS Organism Console & Cognitive OS

export type AppTheme = 'dark' | 'light';
export type UserRole = 'admin' | 'guest';
export type ConsoleView = 'home' | 'dashboard' | 'cli' | 'inspector' | 'user_chat';

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
    normalized_input: string;
    language: string;
    confidence: number;
    basic_intent: Record<string, any>;
    entities: string[];
    metadata: {
      source: string;
      uncertainty: number;
      goal: string | null;
      reason: string;
    };
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
    last_evolution_at: number;
  };
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
export interface ChatMessage {
  id: string;
  sessionId: string;
  sender: 'user' | 'jarvis';
  text: string;
  timestamp: string;
  dateLabel?: string;
  source: 'web' | 'cli' | 'autonomous';
  trace?: TurnTrace;
  traceLog?: any;
  thinkingDurationSeconds?: number;
  thinkingProcess?: string[];
  extractedFact?: {
    subject: string;
    predicate: string;
    value: string;
    confidence?: number;
  };
}

export interface SessionItem {
  sessionId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  pinned: boolean;
  msgCount: number;
  category: 'Today' | 'Yesterday' | 'Previous 7 Days' | 'Previous' | 'Older';
}

export type ChatSession = SessionItem;

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

export type ActiveTab = 'chat' | 'matrix' | 'memory' | 'autonomy' | 'code';

// ==========================================
// SECTION 4: NEW CAPABILITIES INTERFACES
// ==========================================

// 4a. Voice Control & Speech Settings
export interface VoiceSettings {
  pitch: number; // default 0.55
  rate: number; // default 1.1
  language: string; // default 'hi-IN'
  engine: string;
  spoken_replies: boolean;
  whisper_fallback: boolean; // opt-in fallback to Whisper-via-Groq
}

export interface TTSEngine {
  name: string;
  label?: string;
  default?: boolean;
}

// 4b. Organ Introspection (10 fixed questions)
export interface OrganIntrospectionAnswers {
  who_are_you: string;
  responsibility: string;
  received: string;
  produced: string;
  why: string;
  evidence: string;
  confidence: string;
  state_changed: string;
  persisted: string;
  unverified: string;
}

export interface OrganIntrospectionItem {
  organ_name: string;
  displayName: string;
  status: 'active' | 'standby' | 'degraded';
  lastTurnId?: string;
  answers: OrganIntrospectionAnswers;
}

// 4c. Overnight / Idle Learning Report
export interface OvernightFinding {
  id: string;
  pattern_or_vocab: string;
  evidence: string;
  sandbox_tested: boolean;
  test_passed: boolean;
  pass_count: number;
  fail_count: number;
}

export interface OvernightLogEntry {
  timestamp: number;
  reviewed_target: string;
  findings: OvernightFinding[];
  summary: string;
  evidence_threshold_met: boolean;
}

// 4d. Self-Improvement Requests
export interface ImprovementRequest {
  id: string;
  request_text: string;
  timestamp: number;
  scope: 'narrow' | 'broad'; // narrow: JARVIS can sandbox-test; broad: needs developer
  status: 'pending' | 'sandbox_testing' | 'applied' | 'rejected' | 'needs_operator';
  evidence?: string;
  sourceSessionId?: string;
}

// 4e. Runtime / Uptime Telemetry
export interface RuntimeInfo {
  session_uptime_seconds: number; // this process only
  cumulative_runtime_seconds: number; // all sessions ever, persisted
  age_seconds: number; // time since first boot, includes offline time
}

// 4f. Safety Check History (Llama Prompt Guard 2)
export interface SafetyCheckEntry {
  id: string;
  timestamp: number;
  query_preview: string;
  label: 'benign' | 'malicious';
  score?: number;
  action: 'flagged_only' | 'passed';
  notes?: string;
}
