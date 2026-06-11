import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { Repository } from '../types';
import { GitBranch, GitPullRequest, Loader2, Play, AlertCircle, CheckCircle, Database } from 'lucide-react';

interface RepositoryListProps {
  selectedRepoId: string | null;
  onSelectRepo: (repo: Repository | null) => void;
}

export const RepositoryList: React.FC<RepositoryListProps> = ({
  selectedRepoId,
  onSelectRepo,
}) => {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [githubUrl, setGithubUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRepos = async () => {
    try {
      const data = await api.listRepositories();
      setRepos(data.repositories);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchRepos();
    const interval = setInterval(fetchRepos, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl) return;
    setLoading(true);
    setError(null);
    try {
      await api.ingestRepository(githubUrl, branch);
      setGithubUrl('');
      setBranch('main');
      await fetchRepos();
    } catch (err: any) {
      setError(err.message || 'Failed to start ingestion');
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: Repository['status']) => {
    switch (status) {
      case 'pending':
        return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />;
      case 'ingesting':
        return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-rose-500" />;
    }
  };

  const getStatusBadge = (status: Repository['status']) => {
    const baseClass = "px-2 py-0.5 text-xs font-semibold rounded-full flex items-center gap-1 capitalize";
    switch (status) {
      case 'pending':
        return <span className={`${baseClass} bg-amber-400/10 text-amber-400`}>Pending</span>;
      case 'ingesting':
        return <span className={`${baseClass} bg-blue-500/10 text-blue-400`}>Ingesting</span>;
      case 'completed':
        return <span className={`${baseClass} bg-emerald-500/10 text-emerald-400`}>Completed</span>;
      case 'failed':
        return <span className={`${baseClass} bg-rose-500/10 text-rose-400`}>Failed</span>;
    }
  };

  return (
    <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3">
        <Database className="w-5 h-5 text-blue-400" />
        <h2 className="text-md font-semibold text-slate-100">Repositories</h2>
      </div>

      {/* Ingest Form */}
      <form onSubmit={handleIngest} className="space-y-3 mb-6">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">GitHub Repository URL</label>
          <input
            type="text"
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            className="w-full bg-[#181c25] border border-slate-800 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-colors placeholder-slate-600"
            required
          />
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-400 mb-1">Branch</label>
            <div className="relative">
              <input
                type="text"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="w-full bg-[#181c25] border border-slate-800 rounded pl-8 pr-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                required
              />
              <GitBranch className="w-4 h-4 text-slate-500 absolute left-2.5 top-2.5" />
            </div>
          </div>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading || !githubUrl}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded px-4 py-1.5 text-sm font-semibold transition-colors flex items-center gap-1.5 cursor-pointer h-[38px]"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" /> Ingest
                </>
              )}
            </button>
          </div>
        </div>
        {error && (
          <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded text-xs text-rose-400 flex items-start gap-1.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
      </form>

      {/* Repo List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {repos.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">No repositories ingested yet.</div>
        ) : (
          repos.map((repo) => (
            <div
              key={repo.id}
              onClick={() => onSelectRepo(selectedRepoId === repo.id ? null : repo)}
              className={`p-3 rounded-lg border transition-all cursor-pointer ${
                selectedRepoId === repo.id
                  ? 'bg-blue-600/10 border-blue-500'
                  : 'bg-[#181c25] border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="truncate">
                  <h3 className="text-sm font-semibold text-slate-200 truncate">{repo.name}</h3>
                  <p className="text-xs text-slate-400 truncate">{repo.owner}</p>
                </div>
                <div className="flex-shrink-0 mt-0.5">{getStatusIcon(repo.status)}</div>
              </div>
              <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
                <div className="flex items-center gap-1">
                  <GitPullRequest className="w-3.5 h-3.5" />
                  <span>{repo.artifact_count} artifacts</span>
                </div>
                {getStatusBadge(repo.status)}
              </div>
              {repo.error_message && (
                <div className="mt-2 text-2xs text-rose-400 bg-rose-950/20 p-1.5 rounded border border-rose-950/40">
                  {repo.error_message}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
