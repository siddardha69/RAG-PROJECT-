import React, { useState } from 'react';
import { api } from '../services/api';
import type { QueryResponse } from '../types';
import { MessageSquare, Send, Loader2, Link, ShieldAlert, Cpu, Calendar, User } from 'lucide-react';

interface QueryPanelProps {
  selectedRepoId: string | null;
  selectedRepoName: string | null;
  onSelectCitation: (artifactId: string) => void;
}

export const QueryPanel: React.FC<QueryPanelProps> = ({
  selectedRepoId,
  selectedRepoName,
  onSelectCitation,
}) => {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.askQuestion(question, selectedRepoId || undefined, true);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Failed to execute query');
    } finally {
      setLoading(false);
    }
  };

  const getRecBadgeColor = (rec: string) => {
    switch (rec.toLowerCase()) {
      case 'keep':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'revisit':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      case 'replace':
        return 'bg-rose-500/10 text-rose-400 border border-rose-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
    }
  };

  return (
    <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex flex-col">
      {/* Panel Header */}
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-400" />
          <h2 className="text-md font-semibold text-slate-100">Decision Query</h2>
        </div>
        {selectedRepoName && (
          <span className="text-xs px-2.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 truncate max-w-[200px]">
            {selectedRepoName}
          </span>
        )}
      </div>

      {/* Query Results Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4 text-sm scrollbar-thin">
        {!result ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 px-4">
            <Cpu className="w-8 h-8 text-slate-600 mb-2" />
            <p className="text-xs">
              {selectedRepoId
                ? "Ask a question about the architectural choices in this repository."
                : "Select a repository on the left and enter your query."}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Answer Box */}
            <div className="bg-[#181c25] rounded-lg border border-slate-800 p-4 leading-relaxed text-slate-300">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Synthesis</h3>
              <p className="whitespace-pre-line">{result.answer}</p>
            </div>

            {/* Recommendation Guardrails */}
            {result.recommendation && (
              <div className="bg-[#181c25] rounded-lg border border-slate-800 p-4 flex flex-col gap-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                  <span>Recommendation &amp; Risk Guardrails</span>
                </div>
                <div className="flex items-center justify-between bg-slate-900/40 p-2.5 rounded border border-slate-850">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Decision Assessment:</span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold capitalize ${getRecBadgeColor(result.recommendation)}`}>
                      {result.recommendation}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Confidence: <span className="font-bold text-slate-200">{(result.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            )}

            {/* Citations / Sources */}
            {result.citations && result.citations.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider pl-1">Cited Evidence</h3>
                <div className="grid grid-cols-1 gap-2">
                  {result.citations.map((cite) => (
                    <div
                      key={cite.artifact_id}
                      onClick={() => onSelectCitation(cite.artifact_id)}
                      className="bg-[#181c25] hover:bg-[#1f2430] border border-slate-800 hover:border-slate-700 rounded-lg p-3 transition-all cursor-pointer flex flex-col gap-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-bold text-blue-400 uppercase bg-blue-500/10 px-2 py-0.5 rounded flex-shrink-0">
                          {cite.artifact_type.replace('_', ' ')}
                        </span>
                        <span className="text-2xs text-slate-500 font-medium">
                          Relevance: {(cite.relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <h4 className="text-xs font-semibold text-slate-200 line-clamp-1">{cite.title}</h4>
                      <div className="flex items-center gap-4 text-2xs text-slate-500 mt-1">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" /> {cite.author}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" /> {new Date(cite.created_at).toLocaleDateString()}
                        </span>
                        {cite.url && (
                          <a
                            href={cite.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-0.5 text-blue-500 hover:underline ml-auto"
                          >
                            <Link className="w-3 h-3" /> Open
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Latency and Query info */}
            <div className="text-2xs text-slate-600 text-right pt-2 border-t border-slate-850">
              Retrieved in {result.latency_ms}ms
            </div>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="relative mt-auto">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={selectedRepoId ? "Ask: why did we use..." : "Select a repository to begin..."}
          className="w-full bg-[#181c25] border border-slate-800 rounded-lg pl-4 pr-12 py-3 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-colors placeholder-slate-600 disabled:opacity-50"
          disabled={loading || !selectedRepoId}
        />
        <button
          type="submit"
          disabled={loading || !question.trim() || !selectedRepoId}
          className="absolute right-2 top-2 p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-md transition-colors cursor-pointer"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>
      {error && (
        <p className="mt-2 text-xs text-rose-400 bg-rose-950/20 border border-rose-900/30 p-2 rounded">{error}</p>
      )}
    </div>
  );
};
