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
    <aside className="w-80 md:w-96 flex flex-col bg-[#2b2622] border-r border-[#3f3a36] shrink-0 h-full overflow-hidden">
      {/* Search and Filter Header */}
      <div className="p-3 border-b border-[#3f3a36] space-y-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#aea69c]" />
          <input
            type="text"
            placeholder="Search prompts & outputs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-text w-full pl-8 pr-2.5 py-1 text-xs font-mono"
          />
        </div>

        <div className="flex items-center justify-between text-xs">
          {/* Status filter pills */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono transition-colors cursor-pointer ${
                statusFilter === 'all'
                  ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                  : 'text-[#aea69c] hover:text-[#f7f5f0]'
              }`}
            >
              All ({traces.length})
            </button>
            <button
              onClick={() => setStatusFilter('success')}
              className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono transition-colors cursor-pointer ${
                statusFilter === 'success'
                  ? 'bg-[#383330] text-emerald-400 border border-emerald-800/40 font-medium'
                  : 'text-[#aea69c] hover:text-[#f7f5f0]'
              }`}
            >
              OK
            </button>
            <button
              onClick={() => setStatusFilter('error')}
              className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono transition-colors cursor-pointer ${
                statusFilter === 'error'
                  ? 'bg-[#383330] text-rose-400 border border-rose-800/40 font-medium'
                  : 'text-[#aea69c] hover:text-[#f7f5f0]'
              }`}
            >
              Error
            </button>
            <button
              onClick={() => setStatusFilter('safety_blocked')}
              className={`px-2 py-0.5 rounded-[2px] text-[10px] font-mono transition-colors cursor-pointer ${
                statusFilter === 'safety_blocked'
                  ? 'bg-[#383330] text-amber-300 border border-amber-800/40 font-medium'
                  : 'text-[#aea69c] hover:text-[#f7f5f0]'
              }`}
            >
              Blocked
            </button>
          </div>

          {/* Sort order toggle */}
          <button
            onClick={() => setSortAsc(!sortAsc)}
            className="p-1 rounded-[2px] hover:bg-[#383330] text-[#aea69c] hover:text-[#f7f5f0] transition-colors cursor-pointer"
            title={sortAsc ? 'Oldest first (click for newest)' : 'Newest first (click for oldest)'}
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Interactions List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {displayTraces.length === 0 ? (
          <div className="p-8 text-center text-[#aea69c] text-xs font-mono">
            No matching interactions found.
          </div>
        ) : (
          displayTraces.map((trace) => {
            const isSelected = trace.trace_id === selectedTraceId;

            const inputTokens = trace.token_usage?.input_tokens || 0;
            const outputTokens = trace.token_usage?.output_tokens || 0;
            const cachedTokens = trace.token_usage?.cached_tokens || 0;

            return (
              <div
                key={trace.trace_id}
                onClick={() => onSelectTrace(trace.trace_id)}
                className={`p-2.5 rounded-[3px] border text-left cursor-pointer transition-colors border-l-2 ${
                  isSelected
                    ? 'bg-[#383330] border-[#544d47] border-l-[#f7f5f0] text-[#f7f5f0]'
                    : 'bg-[#24201d] border-[#3f3a36] hover:bg-[#383330]/50 border-l-transparent text-[#dad2c1]'
                }`}
              >
                {/* Header row: Agent name + status icon + time */}
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#dad2c1] border border-[#3f3a36]">
                      {trace.agent}
                    </span>
                    {trace.iteration > 1 && (
                      <span className="text-[10px] font-mono px-1 py-0.2 rounded-[2px] bg-[#2b2622] text-[#aea69c] border border-[#3f3a36]">
                        Pass {trace.iteration}
                      </span>
                    )}
                    {trace.total_chunks > 1 && (
                      <span className="text-[10px] font-mono px-1 py-0.2 rounded-[2px] bg-[#2b2622] text-[#aea69c] border border-[#3f3a36]">
                        [{trace.chunk_index}/{trace.total_chunks}]
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
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    )}
                  </div>
                </div>

                {/* Model & Stage */}
                <div className="flex items-center justify-between text-[10px] font-mono text-[#aea69c] mb-1.5">
                  <span className="truncate max-w-[150px]">
                    {trace.model}
                  </span>
                  <span className="capitalize">
                    {trace.stage}
                  </span>
                </div>

                {/* Excerpt Snippet */}
                <div className="text-[11px] font-mono text-[#c9c0ad] line-clamp-2 mb-1.5 leading-relaxed">
                  {cleanPreviewSnippet(trace.raw_output || trace.user_prompt)}
                </div>

                {/* Footer stats: tokens & duration */}
                <div className="flex items-center justify-between pt-1.5 border-t border-[#3f3a36] text-[10px] font-mono text-[#aea69c]">
                  <div className="flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-[#aea69c]" />
                    <span>
                      {inputTokens.toLocaleString()} in / {outputTokens.toLocaleString()} out
                      {cachedTokens > 0 && (
                        <span className="text-cyan-300 font-semibold ml-1">
                          · ⚡{cachedTokens.toLocaleString()}
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-[#aea69c]" />
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
