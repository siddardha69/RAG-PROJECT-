import type {
  Repository,
  QueryResponse,
  TimelineResponse,
  RecommendationResponse,
  GraphData,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export const api = {
  // Repositories
  async listRepositories(skip = 0, limit = 20): Promise<{ repositories: Repository[]; total: number }> {
    const res = await fetch(`${API_BASE}/api/repositories?skip=${skip}&limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch repositories');
    return res.json();
  },

  async getRepository(id: string): Promise<Repository> {
    const res = await fetch(`${API_BASE}/api/repositories/${id}`);
    if (!res.ok) throw new Error('Failed to fetch repository details');
    return res.json();
  },

  async ingestRepository(githubUrl: string, branch = 'main'): Promise<{ repository_id: string; status: string }> {
    const res = await fetch(`${API_BASE}/api/repositories/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ github_url: githubUrl, branch }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Failed to trigger repository ingestion');
    }
    return res.json();
  },

  // Queries (GraphRAG)
  async askQuestion(
    question: string,
    repositoryId?: string,
    includeRecommendations = true
  ): Promise<QueryResponse> {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        repository_id: repositoryId || null,
        include_recommendations: includeRecommendations,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Query execution failed');
    }
    return res.json();
  },

  // Timelines
  async getTimeline(artifactId: string): Promise<TimelineResponse> {
    const res = await fetch(`${API_BASE}/api/timeline/${artifactId}`);
    if (!res.ok) throw new Error('Failed to load decision timeline');
    return res.json();
  },

  // Recommendations
  async getRecommendation(artifactId: string): Promise<RecommendationResponse> {
    const res = await fetch(`${API_BASE}/api/recommendations/${artifactId}`);
    if (!res.ok) throw new Error('Failed to load risk recommendation');
    return res.json();
  },

  // Graph Visualization
  async getGraphData(repositoryName: string): Promise<GraphData> {
    const res = await fetch(`${API_BASE}/api/recommendations/graph?repository_name=${encodeURIComponent(repositoryName)}`);
    if (!res.ok) throw new Error('Failed to load repository graph data');
    return res.json();
  },
};
