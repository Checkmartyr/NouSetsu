import React, { useState } from 'react';
import { AgentPromptTrace } from '../types/trace';
import { cleanPreviewSnippet } from '../utils/jsonParser';
import { Search, Cpu, Clock, CheckCircle2, AlertTriangle, ShieldAlert, ArrowUpDown } from 'lucide-react';

interface TraceTimelineProps {
  traces: AgentPromptTrace[];
  selectedTraceId: string | null;
  onSelectTrace: (traceId: string) => void;
  selectedStageFilter: string | null;
}

const AGENT_THEMES: Record<string, { badge: string; border: string }> = {
  extractor: { badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30', border: 'border-l-amber-500' },
  drafter: { badge: 'bg-blue-500/10 text-blue-400 border-blue-500/30', border: 'border-l-blue-500' },
  critique: { badge: 'bg-purple-500/10 text-purple-400 border-purple-500/30', border: 'border-l-purple-500' },
  polisher: { badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', border: 'border-l-emerald-500' },
  chronicler: { badge: 'bg-rose-500/10 text-rose-400 border-rose-500/30', border: 'border-l-rose-500' },
};

export const TraceTimeline: React.FC<TraceTimelineProps> = ({
  traces,
  selectedTraceId,
  onSelectTrace,
  selectedStageFilter,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'safety_blocked' | 'error'>('all');
  const [sortAsc, setSortAsc] = useState(true);

  // Filter traces
  const filteredTraces = traces.filter((t) => {
    if (selectedStageFilter && t.stage !== selectedStageFilter) {
      return false;
    }
    if (statusFilter !== 'all' && t.status !== statusFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchAgent = t.agent.toLowerCase().includes(q);
      const matchModel = t.model.toLowerCase().includes(q);
      const matchStage = t.stage.toLowerCase().includes(q);
      const matchPrompt = t.user_prompt.toLowerCase().includes(q) || t.system_prompt.toLowerCase().includes(q);
      const matchOutput = (t.raw_output || '').toLowerCase().includes(q);
      return matchAgent || matchModel || matchStage || matchPrompt || matchOutput;
    }
    return true;
  });

  const displayTraces = sortAsc ? filteredTraces : [...filteredTraces].reverse();

  return (
    <aside className="w-80 md:w-96 flex flex-col bg-slate-900/60 border-r border-slate-800 shrink-0 h-full overflow-hidden">
      {/* Search and Filter Header */}
      <div className="p-3 border-b border-slate-800 space-y-2">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search prompts & outputs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center justify-between text-xs">
          {/* Status filter pills */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                statusFilter === 'all'
                  ? 'bg-slate-700 text-slate-100 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All ({traces.length})
            </button>
            <button
              onClick={() => setStatusFilter('success')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                statusFilter === 'success'
                  ? 'bg-emerald-500/20 text-emerald-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              OK
            </button>
            <button
              onClick={() => setStatusFilter('error')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                statusFilter === 'error'
                  ? 'bg-red-500/20 text-red-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Error
            </button>
            <button
              onClick={() => setStatusFilter('safety_blocked')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                statusFilter === 'safety_blocked'
                  ? 'bg-amber-500/20 text-amber-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Blocked
            </button>
          </div>

          {/* Sort order toggle */}
          <button
            onClick={() => setSortAsc(!sortAsc)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title={sortAsc ? 'Oldest first (click for newest)' : 'Newest first (click for oldest)'}
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Interactions List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {displayTraces.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            No matching interactions found.
          </div>
        ) : (
          displayTraces.map((trace) => {
            const isSelected = trace.trace_id === selectedTraceId;
            const theme = AGENT_THEMES[trace.agent] || {
              badge: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
              border: 'border-l-indigo-500',
            };

            const inputTokens = trace.token_usage?.input_tokens || 0;
            const outputTokens = trace.token_usage?.output_tokens || 0;
            const cachedTokens = trace.token_usage?.cached_tokens || 0;

            return (
              <div
                key={trace.trace_id}
                onClick={() => onSelectTrace(trace.trace_id)}
                className={`p-3 rounded-xl border text-left cursor-pointer transition-all border-l-4 ${theme.border} ${
                  isSelected
                    ? 'bg-slate-800 border-slate-700 shadow-md ring-1 ring-indigo-500/50'
                    : 'bg-slate-950/60 border-slate-800/80 hover:bg-slate-850 hover:border-slate-700'
                }`}
              >
                {/* Header row: Agent name + status icon + time */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${theme.badge}`}>
                      {trace.agent}
                    </span>
                    {trace.iteration > 1 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold">
                        Pass {trace.iteration}
                      </span>
                    )}
                    {trace.total_chunks > 1 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-medium">
                        [{trace.chunk_index}/{trace.total_chunks}]
                      </span>
                    )}
                    {trace.depth > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-medium">
                        D:{trace.depth}
                      </span>
                    )}
                  </div>

                  {/* Status indicator */}
                  <div>
                    {trace.status === 'success' && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    {trace.status === 'safety_blocked' && (
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                    )}
                    {trace.status === 'error' && (
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    )}
                  </div>
                </div>

                {/* Model & Stage */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 mb-2">
                  <span className="truncate max-w-[140px] font-mono text-[10px] text-slate-500">
                    {trace.model}
                  </span>
                  <span className="capitalize text-slate-400 font-medium">
                    {trace.stage}
                  </span>
                </div>

                {/* Excerpt Snippet */}
                <div className="text-xs text-slate-300 line-clamp-2 mb-2 font-serif-prose leading-relaxed">
                  {cleanPreviewSnippet(trace.raw_output || trace.user_prompt)}
                </div>

                {/* Footer stats: tokens & duration */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[10px] text-slate-400">
                  <div className="flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-slate-500" />
                    <span>
                      {inputTokens.toLocaleString()} in / {outputTokens.toLocaleString()} out
                      {cachedTokens > 0 && (
                        <span className="text-cyan-400 font-semibold ml-1">
                          · ⚡{cachedTokens.toLocaleString()}
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <span>{trace.duration_seconds.toFixed(2)}s</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
