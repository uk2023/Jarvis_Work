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
