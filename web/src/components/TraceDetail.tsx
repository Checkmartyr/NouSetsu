import React, { useState } from 'react';
import { AgentPromptTrace, ChapterTraceDocument } from '../types/trace';
import { PromptViewer } from './PromptViewer';
import { OutputViewer } from './OutputViewer';
import { DiffViewer } from './DiffViewer';
import { TokenAnalytics } from './TokenAnalytics';
import { Terminal, FileText, GitCompare, BarChart3, Code, Clock, Cpu, Calendar, Coins } from 'lucide-react';
import { calculateCost } from '../utils/pricing';

export type DetailTab = 'prompts' | 'output' | 'diff' | 'analytics' | 'raw';

interface TraceDetailProps {
  trace: AgentPromptTrace;
  chapterDoc: ChapterTraceDocument;
  activeTab?: DetailTab;
  onTabChange?: (tab: DetailTab) => void;
}

export const TraceDetail: React.FC<TraceDetailProps> = ({
  trace,
  chapterDoc,
  activeTab: controlledTab,
  onTabChange,
}) => {
  const [internalTab, setInternalTab] = useState<DetailTab>('output');
  const activeTab = controlledTab !== undefined ? controlledTab : internalTab;

  const hasDiffAvailable =
    chapterDoc.traces.some((t) => t.stage?.toLowerCase() === 'drafting') &&
    chapterDoc.traces.some((t) => t.stage?.toLowerCase() === 'polishing');

  const handleTabSelect = (tab: DetailTab) => {
    if (onTabChange) {
      onTabChange(tab);
    } else {
      setInternalTab(tab);
    }
  };

  const formattedDate = new Date(trace.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <main className="flex-1 flex flex-col bg-[#2b2622] overflow-hidden">
      {/* Detail Header / Metadata Ribbon */}
      <div className="bg-[#2b2622] border-b border-[#3f3a36] px-6 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#f7f5f0] border border-[#3f3a36]">
              {trace.agent}
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#dad2c1] border border-[#3f3a36] capitalize">
              {trace.stage}
            </span>
            {trace.iteration > 1 && (
              <span className="text-xs font-mono px-1.5 py-0.5 rounded-[2px] bg-[#383330] text-[#aea69c] border border-[#3f3a36]">
                Pass {trace.iteration}
              </span>
            )}
            {trace.total_chunks > 1 && (
              <span className="text-xs font-mono px-1.5 py-0.5 rounded-[2px] bg-[#383330] text-[#aea69c] border border-[#3f3a36]">
                Chunk {trace.chunk_index}/{trace.total_chunks}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2.5 text-xs text-[#aea69c] font-mono">
            <div className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-[#aea69c]" />
              <span>{formattedDate}</span>
            </div>
            <div className="px-2 py-0.5 rounded-[2px] bg-[#383330] border border-[#3f3a36] text-[#dad2c1] text-[11px]">
              {trace.model}
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-[#aea69c]" />
              <span>{trace.duration_seconds.toFixed(2)}s</span>
            </div>
            <div className="flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5 text-[#aea69c]" />
              <span>{(trace.token_usage?.total_tokens || 0).toLocaleString()} tok</span>
              {trace.token_usage?.cached_tokens > 0 && (
                <span className="text-cyan-300 text-[10px] font-semibold bg-[#24201d] border border-[#3f3a36] px-1.5 py-0.2 rounded ml-1">
                  ⚡ {trace.token_usage.cached_tokens.toLocaleString()}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 text-[#f7f5f0] bg-[#383330] border border-[#3f3a36] px-2 py-0.5 rounded-[2px] text-[11px]">
              <Coins className="w-3 h-3 text-[#f7f5f0]" />
              <span>{calculateCost(trace.token_usage || {}, trace.model || 'unknown').formattedTotal}</span>
            </div>
          </div>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-1 mt-2.5 pt-2 border-t border-[#3f3a36]">
          <button
            onClick={() => handleTabSelect('output')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'output'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Output</span>
          </button>

          <button
            onClick={() => handleTabSelect('prompts')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'prompts'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Prompts</span>
          </button>

          <button
            onClick={() => handleTabSelect('diff')}
            title={
              hasDiffAvailable
                ? "Compare raw draft prose against polished prose"
                : "Diff comparison requires drafting and polishing traces"
            }
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'diff'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Diff Comparison</span>
            {hasDiffAvailable && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block ml-0.5" />
            )}
          </button>

          <button
            onClick={() => handleTabSelect('analytics')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'analytics'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Token & Latency Analytics</span>
          </button>

          <button
            onClick={() => handleTabSelect('raw')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ml-auto ${
              activeTab === 'raw'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>Raw JSON</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 p-6 overflow-hidden">
        {activeTab === 'output' && <OutputViewer trace={trace} />}
        {activeTab === 'prompts' && <PromptViewer trace={trace} />}
        {activeTab === 'diff' && (
          <DiffViewer currentTrace={trace} allTraces={chapterDoc.traces} />
        )}
        {activeTab === 'analytics' && (
          <TokenAnalytics currentTrace={trace} chapterDoc={chapterDoc} />
        )}
        {activeTab === 'raw' && (
          <div className="h-full bg-[#24201d] border border-[#3f3a36] rounded-[4px] p-4 overflow-y-auto font-mono text-xs text-[#dad2c1]">
            <pre>{JSON.stringify(trace, null, 2)}</pre>
          </div>
        )}
      </div>
    </main>
  );
};
