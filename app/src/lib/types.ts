export interface DocumentSummary {
  id: string;
  title: string;
  file_type: string;
  term: string | null;
  course: string | null;
  course_code: string | null;
  category: string | null;
  material_type: string | null;
  page_count: number | null;
  status: "pending" | "indexed" | "error";
  error_message: string | null;
  imported_at: string | null;
  last_indexed_at: string | null;
}

export interface DocumentChunkView {
  chunk_index: number;
  page_number: number | null;
  slide_number: number | null;
  text: string;
}

export interface DocumentDetail extends DocumentSummary {
  chunks: DocumentChunkView[];
}

export interface RepositoryStats {
  total: number;
  indexed: number;
  errored: number;
  by_category: Record<string, number>;
  by_term: Record<string, number>;
}

export interface ImportJobStatus {
  id: string;
  status: "running" | "done";
  total: number;
  processed: number;
  indexed: number;
  skipped_duplicates: number;
  errors: { file: string; error: string }[];
  current_file: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface TermInfo {
  name: string;
  courses: string[];
}

export interface AgentPermissionView {
  resource_type: string;
  resource_value: string;
  access_level: string;
}

export interface AgentView {
  id: string;
  slug: string;
  name: string;
  description: string;
  purpose: string;
  owner: string;
  status: "active" | "suspended" | "deactivated";
  permitted_tools: string[];
  restricted_actions: string[];
  permissions: AgentPermissionView[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ConversationView {
  id: string;
  agent_id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  title: string;
  course: string | null;
  page_number: number | null;
  slide_number: number | null;
  snippet: string;
}

export interface GovernanceNote {
  document_id?: string;
  title?: string;
  decision: string;
  reason: string;
}

export interface MemoryUsed {
  memory_id: string;
  title: string;
  description: string;
  memory_type: string;
  topic: string | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  governance_notes: GovernanceNote[];
  memories_used: MemoryUsed[];
  created_at: string | null;
}

export interface MemoryView {
  id: string;
  memory_type: "knowledge" | "episodic" | "user_context" | "decision";
  title: string;
  description: string;
  topic: string | null;
  agent_id: string | null;
  conversation_id: string | null;
  confidence: number;
  approval_status: "pending" | "approved" | "rejected";
  created_at: string | null;
  sources?: { source_type: string; source_id: string }[];
}

export interface ApprovalView {
  id: string;
  agent_id: string;
  agent_name: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  reason: string;
  policy_id: string | null;
  status: "pending" | "approved" | "rejected";
  decided_by: string | null;
  decided_at: string | null;
  created_at: string | null;
  resource_preview?: {
    memory_type: string;
    title: string;
    description: string;
    topic: string | null;
  };
}

export interface AuditEventView {
  id: string;
  timestamp: string | null;
  agent_id: string | null;
  agent_name: string;
  session_id: string | null;
  event_type: string;
  resource_id: string | null;
  requested_action: string | null;
  policy_evaluated: string | null;
  decision: string | null;
  reason: string | null;
  approval_ref: string | null;
  hash: string;
}

export interface GraphNodeView {
  id: string;
  node_type: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdgeView {
  id: string;
  source: string;
  target: string;
  relation: string;
  confidence: number;
  provenance: "inferred" | "confirmed";
}

export interface GraphOverview {
  nodes: GraphNodeView[];
  edges: GraphEdgeView[];
  stats: { node_count: number; edge_count: number };
}

export interface GraphConnection {
  edge_id: string;
  relation: string;
  direction: "outgoing" | "incoming";
  provenance: "inferred" | "confirmed";
  confidence: number;
  node: { id: string; node_type: string; label: string };
}

export interface GraphNodeDetail extends GraphNodeView {
  connections: GraphConnection[];
}

export interface GraphSourceDocument {
  id: string;
  title: string;
  file_type: string;
  term: string | null;
  course: string | null;
  category: string | null;
  page_count: number | null;
  file_url: string | null;
}

export interface GraphBuildStatus {
  id: string;
  status: "running" | "done";
  total: number;
  processed: number;
  nodes_created: number;
  edges_created: number;
  errors: { document: string; error: string }[];
  started_at: string;
  finished_at: string | null;
}

export interface OverviewData {
  documents: { total: number; indexed: number };
  knowledge_graph: { nodes: number; edges: number };
  agents: { active: number; total: number };
  memories_stored: number;
  pending_approvals: number;
  recent_events: {
    id: string;
    timestamp: string | null;
    agent_name: string;
    event_type: string;
    decision: string | null;
    reason: string | null;
  }[];
}

export interface SearchResult {
  chunk_id: string;
  snippet: string;
  document_id: string;
  title: string;
  course: string | null;
  page_number: number | null;
  slide_number: number | null;
  score: number;
}
