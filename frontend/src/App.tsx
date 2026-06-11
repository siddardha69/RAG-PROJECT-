import { useState } from 'react';
import type { Repository } from './types';
import { RepositoryList } from './components/RepositoryList';
import { QueryPanel } from './components/QueryPanel';
import { TimelinePanel } from './components/TimelinePanel';
import { GraphPanel } from './components/GraphPanel';
import { Brain, Cpu, RefreshCw } from 'lucide-react';

function App() {
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);

  const handleSelectRepo = (repo: Repository | null) => {
    setSelectedRepo(repo);
    // Clear selected artifact when repo changes
    setSelectedArtifactId(null);
  };

  const handleSelectCitation = (artifactId: string) => {
    setSelectedArtifactId(artifactId);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0d0f12] text-slate-100 font-sans overflow-hidden">
      {/* Header */}
      <header className="bg-[#11141b] border-b border-slate-800 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600/20 p-2 rounded-lg border border-blue-500/30">
            <Brain className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              ArchaeologAI
            </h1>
            <p className="text-2xs text-slate-400 font-medium">
              GraphRAG Codebase Architectural Historian &amp; Decision Lineage
            </p>
          </div>
        </div>

        {/* Global Stats or Status */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Cpu className="w-4 h-4 text-blue-500" />
            <span>AI Status: <strong className="text-emerald-400">Online</strong></span>
          </div>
          <button 
            onClick={() => window.location.reload()} 
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg border border-slate-850 hover:border-slate-800 bg-[#161a22]/40 transition-all cursor-pointer"
            title="Refresh dashboard"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Main Dashboard Layout */}
      <main className="flex-1 flex gap-4 p-4 overflow-hidden min-h-0 bg-[#0d0f12]">
        {/* Column 1: Repositories */}
        <div className="w-[300px] flex-shrink-0 h-full">
          <RepositoryList
            selectedRepoId={selectedRepo ? selectedRepo.id : null}
            onSelectRepo={handleSelectRepo}
          />
        </div>

        {/* Column 2: Query Executions */}
        <div className="w-[420px] flex-shrink-0 h-full">
          <QueryPanel
            selectedRepoId={selectedRepo ? selectedRepo.id : null}
            selectedRepoName={selectedRepo ? `${selectedRepo.owner}/${selectedRepo.name}` : null}
            onSelectCitation={handleSelectCitation}
          />
        </div>

        {/* Column 3: Chronological Timelines & Graph Visualizer */}
        <div className="flex-1 flex flex-col gap-4 h-full min-w-0">
          {/* Top Half: Timeline & Recommendation */}
          <div className="h-[45%] flex-shrink-0">
            <TimelinePanel artifactId={selectedArtifactId} />
          </div>

          {/* Bottom Half: React Flow Subgraph Visualizer */}
          <div className="flex-1 min-h-0">
            <GraphPanel repositoryName={selectedRepo ? selectedRepo.name : null} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
