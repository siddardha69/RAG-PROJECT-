export interface Repository {
  id: string;
  github_url: string;
  owner: string;
  name: string;
  description: string | null;
  status: 'pending' | 'ingesting' | 'completed' | 'failed';
  artifact_count: number;
  created_at: string;
  updated_at: string;
  last_ingested_at: string | null;
  error_message: string | null;
}

export interface ArtifactCitation {
  artifact_id: string;
  artifact_type: string;
  title: string;
  url: string | null;
  author: string;
  created_at: string;
  relevance_score: number;
}

export interface QueryResponse {
  question: string;
  answer: string;
  citations: ArtifactCitation[];
  timeline_summary: any[];
  recommendation: string | null;
  confidence: number;
  latency_ms: number;
  query_log_id: string;
}

export interface RecommendationResponse {
  id: string;
  artifact_id: string;
  original_assumption: string;
  current_risk: string;
  recommendation: 'keep' | 'revisit' | 'replace';
  confidence: number;
  created_at: string;
}

export interface TimelineEvent {
  event_date: string;
  event_type: string;
  title: string;
  description: string;
  artifact_id: string;
  artifact_type: string;
  author: string;
  url: string | null;
}

export interface TimelineResponse {
  artifact_id: string;
  events: TimelineEvent[];
  narrative: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
