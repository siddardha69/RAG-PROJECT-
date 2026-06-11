import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { TimelineResponse, RecommendationResponse } from '../types';
import { Clock, Loader2, Calendar, User, Link, Shield, AlertTriangle, HelpCircle } from 'lucide-react';

interface TimelinePanelProps {
  artifactId: string | null;
}

export const TimelinePanel: React.FC<TimelinePanelProps> = ({ artifactId }) => {
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!artifactId) {
      setTimeline(null);
      setRecommendation(null);
      return;
    }

    const loadTimelineData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [timelineData, recData] = await Promise.all([
          api.getTimeline(artifactId),
          api.getRecommendation(artifactId).catch(() => null), // Fallback if no recommendation found
        ]);
        setTimeline(timelineData);
        setRecommendation(recData);
      } catch (err: any) {
        setError(err.message || 'Failed to load timeline details');
      } finally {
        setLoading(false);
      }
    };

    loadTimelineData();
  }, [artifactId]);

  const getRecommendationStyle = (rec: string) => {
    switch (rec.toLowerCase()) {
      case 'keep':
        return {
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          icon: <Shield className="w-5 h-5 text-emerald-400" />,
        };
      case 'revisit':
        return {
          bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
          icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
        };
      case 'replace':
        return {
          bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
          icon: <AlertTriangle className="w-5 h-5 text-rose-400" />,
        };
      default:
        return {
          bg: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
          icon: <HelpCircle className="w-5 h-5 text-slate-400" />,
        };
    }
  };

  if (loading) {
    return (
      <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex items-center justify-center">
        <div className="text-center text-slate-400 space-y-2">
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-500" />
          <p className="text-xs">Loading decision timeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex items-center justify-center">
        <div className="text-center text-rose-400 space-y-2">
          <AlertTriangle className="w-6 h-6 mx-auto" />
          <p className="text-xs">{error}</p>
        </div>
      </div>
    );
  }

  if (!artifactId || !timeline) {
    return (
      <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex flex-col items-center justify-center text-center text-slate-500">
        <Clock className="w-8 h-8 text-slate-600 mb-2" />
        <h3 className="text-sm font-semibold text-slate-400">Trace Decisions</h3>
        <p className="text-xs max-w-xs mt-1">
          Click on any cited evidence in the query panel to trace its historical lineage, risk assessment, and dependencies.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-[#11141b] rounded-lg border border-slate-800 p-4 h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3 flex-shrink-0">
        <Clock className="w-5 h-5 text-blue-400" />
        <h2 className="text-md font-semibold text-slate-100">Decision Lineage &amp; Risk</h2>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 pr-1 text-sm scrollbar-thin">
        {/* Recommendation Risk assessment */}
        {recommendation && (
          <div className={`p-4 rounded-lg border ${getRecommendationStyle(recommendation.recommendation).bg}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                {getRecommendationStyle(recommendation.recommendation).icon}
                <span className="font-bold text-xs uppercase tracking-wider">
                  Risk Recommendation: {recommendation.recommendation}
                </span>
              </div>
              <div className="text-2xs opacity-80">
                Confidence: <strong>{(recommendation.confidence * 100).toFixed(0)}%</strong>
              </div>
            </div>
            <div className="mt-3 space-y-2.5 text-xs text-slate-200 border-t border-white/10 pt-2.5">
              <div>
                <strong className="text-white">Original Assumption:</strong>
                <p className="mt-0.5 opacity-90">{recommendation.original_assumption}</p>
              </div>
              <div>
                <strong className="text-white">Current Risk Profile:</strong>
                <p className="mt-0.5 opacity-90">{recommendation.current_risk}</p>
              </div>
              <div>
                <strong className="text-white">Actionable Recommendation:</strong>
                <p className="mt-0.5 opacity-90">{recommendation.recommendation}</p>
              </div>
            </div>
          </div>
        )}

        {/* Narrative Summary */}
        <div className="bg-[#181c25] border border-slate-800 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Narrative Summary</h3>
          <p className="text-slate-350 leading-relaxed text-xs whitespace-pre-line">{timeline.narrative}</p>
        </div>

        {/* Timeline Events */}
        <div className="space-y-4 relative pl-3.5 before:content-[''] before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-[2px] before:bg-slate-800">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider pl-0.5 mb-3">Chronological Events</h3>
          {timeline.events.map((evt, idx) => (
            <div key={idx} className="relative group">
              {/* Event node dot */}
              <div className="absolute -left-[18px] top-1 w-2.5 h-2.5 rounded-full bg-blue-500 border border-[#11141b] group-hover:bg-blue-400 transition-colors" />

              <div className="bg-[#181c25] border border-slate-800 group-hover:border-slate-700 rounded-lg p-3 transition-colors">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-bold text-slate-100">{evt.title}</span>
                  <span className="text-3xs uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-semibold">
                    {evt.event_type}
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed mb-2">{evt.description}</p>
                <div className="flex items-center gap-3 text-3xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <User className="w-2.5 h-2.5" /> {evt.author}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-2.5 h-2.5" /> {new Date(evt.event_date).toLocaleDateString()}
                  </span>
                  {evt.url && (
                    <a
                      href={evt.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-0.5 text-blue-500 hover:underline ml-auto"
                    >
                      <Link className="w-2.5 h-2.5" /> View Github
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
