import React, { useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../services/api';
import { GitMerge, Loader2, Network, ShieldAlert } from 'lucide-react';

interface GraphPanelProps {
  repositoryName: string | null;
}

export const GraphPanel: React.FC<GraphPanelProps> = ({ repositoryName }) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeData, setSelectedNodeData] = useState<any | null>(null);

  useEffect(() => {
    if (!repositoryName) {
      setNodes([]);
      setEdges([]);
      setSelectedNodeData(null);
      return;
    }

    const loadGraph = async () => {
      setLoading(true);
      setError(null);
      try {
        const graphData = await api.getGraphData(repositoryName);

        // Group nodes by type to layout them in columns
        const nodeTypes: Record<string, any[]> = {};
        graphData.nodes.forEach((n) => {
          const type = n.type.toLowerCase();
          if (!nodeTypes[type]) nodeTypes[type] = [];
          nodeTypes[type].push(n);
        });

        // Compute layout positions for left-to-right lineage mapping
        const typeIndex: Record<string, number> = {};
        const renderedNodes: Node[] = graphData.nodes.map((node) => {
          const type = node.type.toLowerCase();
          if (typeIndex[type] === undefined) typeIndex[type] = 0;
          const index = typeIndex[type]++;
          const count = nodeTypes[type].length;

          // X Column distribution
          let x = 100;
          if (type.includes('adr')) x = 50;
          else if (type.includes('issue')) x = 250;
          else if (type.includes('pullrequest') || type.includes('pr') || type.includes('commit')) x = 450;
          else if (type.includes('file')) x = 650;
          else if (type.includes('service')) x = 850;
          else x = 1050;

          // Y coordinate distribution
          const height = 400;
          const step = count > 1 ? height / (count + 1) : height / 2;
          const y = step * (index + 1) + 40;

          // styling colors based on type
          let bgColor = '#1e293b';
          let borderColor = '#475569';
          let textColor = '#f8fafc';

          if (type.includes('adr')) {
            bgColor = '#064e3b';
            borderColor = '#059669';
          } else if (type.includes('issue')) {
            bgColor = '#7c2d12';
            borderColor = '#ea580c';
          } else if (type.includes('pullrequest') || type.includes('pr')) {
            bgColor = '#4c1d95';
            borderColor = '#8b5cf6';
          } else if (type.includes('commit')) {
            bgColor = '#1e1b4b';
            borderColor = '#6366f1';
          } else if (type.includes('file')) {
            bgColor = '#164e63';
            borderColor = '#0891b2';
          } else if (type.includes('service')) {
            bgColor = '#78350f';
            borderColor = '#d97706';
          }

          return {
            id: node.id,
            position: { x, y },
            data: {
              label: (
                <div className="text-left max-w-[160px] truncate">
                  <div className="text-3xs uppercase font-bold tracking-wider opacity-60">
                    {node.type}
                  </div>
                  <div className="text-xs font-semibold mt-0.5 truncate">{node.label}</div>
                </div>
              ),
              raw: node,
            },
            style: {
              background: bgColor,
              border: `2.5px solid ${borderColor}`,
              color: textColor,
              padding: '8px 12px',
              borderRadius: '8px',
              width: 180,
            },
          };
        });

        // Format edges with animated flow indicator arrows
        const renderedEdges: Edge[] = graphData.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
          animated: true,
          labelStyle: { fill: '#94a3b8', fontSize: 9, fontWeight: 600, background: '#0d0f12' },
          style: { stroke: '#4b5563', strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 12,
            height: 12,
            color: '#4b5563',
          },
        }));

        setNodes(renderedNodes);
        setEdges(renderedEdges);
      } catch (err: any) {
        setError(err.message || 'Failed to load repository graph visual');
      } finally {
        setLoading(false);
      }
    };

    loadGraph();
  }, [repositoryName]);

  const onNodeClick = (_event: React.MouseEvent, node: Node) => {
    setSelectedNodeData(node.data.raw);
  };

  const onPaneClick = () => {
    setSelectedNodeData(null);
  };

  return (
    <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex flex-col overflow-hidden relative">
      <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3 flex-shrink-0">
        <Network className="w-5 h-5 text-blue-400" />
        <h2 className="text-md font-semibold text-slate-100">Architecture &amp; Lineage Map</h2>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-slate-400 space-y-2">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-500" />
            <p className="text-xs">Visualizing graph structures...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-rose-400 space-y-2">
            <ShieldAlert className="w-6 h-6 mx-auto" />
            <p className="text-xs">{error}</p>
          </div>
        </div>
      ) : !repositoryName ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-500">
          <Network className="w-8 h-8 text-slate-600 mb-2" />
          <h3 className="text-sm font-semibold text-slate-400">Map Connections</h3>
          <p className="text-xs max-w-xs mt-1">
            Select an ingested repository to render its Neo4j knowledge graph relationships.
          </p>
        </div>
      ) : nodes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-500">
          <GitMerge className="w-8 h-8 text-slate-600 mb-2" />
          <h3 className="text-sm font-semibold text-slate-400">No Graph Data</h3>
          <p className="text-xs max-w-xs mt-1">
            The graph database does not have relationships for this repository. Try run a query first.
          </p>
        </div>
      ) : (
        <div className="flex-1 relative border border-slate-800/60 rounded-lg overflow-hidden bg-[#0d0f12]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            fitView
            minZoom={0.5}
            maxZoom={1.5}
          >
            <Background color="#1e293b" gap={16} size={1} />
            <Controls className="bg-slate-900 border border-slate-800" />
            <MiniMap
              nodeColor={() => '#1e293b'}
              maskColor="rgba(15, 23, 42, 0.6)"
              className="bg-slate-900 border border-slate-800"
            />
          </ReactFlow>

          {/* Selection Detail Overlay */}
          {selectedNodeData && (
            <div className="absolute top-4 right-4 bg-[#11141b]/95 border border-slate-700/80 rounded-lg p-4 w-[280px] shadow-2xl z-10 text-xs backdrop-blur-md">
              <div className="flex items-center justify-between border-b border-slate-850 pb-2 mb-2">
                <span className="font-bold text-blue-400 uppercase tracking-wide">
                  {selectedNodeData.type}
                </span>
                <button
                  onClick={() => setSelectedNodeData(null)}
                  className="text-slate-500 hover:text-slate-300 font-bold"
                >
                  &times;
                </button>
              </div>
              <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                <div>
                  <strong className="text-slate-400">Label:</strong>
                  <p className="text-slate-250 font-medium mt-0.5">{selectedNodeData.label}</p>
                </div>
                {Object.entries(selectedNodeData.properties || {}).map(([key, val]: any) => (
                  <div key={key}>
                    <strong className="text-slate-400 capitalize">{key.replace('_', ' ')}:</strong>
                    <p className="text-slate-200 mt-0.5 break-all max-h-[80px] overflow-y-auto">
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
