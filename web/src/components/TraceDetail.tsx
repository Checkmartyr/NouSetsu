import React, { useState } from 'react';
import { AgentPromptTrace, ChapterTraceDocument } from '../types/trace';
import { PromptViewer } from './PromptViewer';
import { OutputViewer } from './OutputViewer';
import { DiffViewer } from './DiffViewer';
import { TokenAnalytics } from './TokenAnalytics';
import { Terminal, FileText, GitCompare, BarChart3, Code, Clock, Cpu, Calendar } from 'lucide-react';

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
    <main className="flex-1 flex flex-col bg-slate-950/60 overflow-hidden">
      {/* Detail Header / Metadata Ribbon */}
      <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-sm font-bold uppercase tracking-wider text-slate-100 bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-700">
              {trace.agent}
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 capitalize">
              {trace.stage}
            </span>
            {trace.iteration > 1 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                Iteration {trace.iteration}
              </span>
            )}
            {trace.total_chunks > 1 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                Chunk {trace.chunk_index}/{trace.total_chunks}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <div className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-slate-500" />
              <span>{formattedDate}</span>
            </div>
            <div className="flex items-center gap-1 font-mono text-[11px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
              {trace.model}
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span>{trace.duration_seconds.toFixed(2)}s</span>
            </div>
            <div className="flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5 text-slate-500" />
              <span>{(trace.token_usage?.total_tokens || 0).toLocaleString()} tok</span>
              {trace.token_usage?.cached_tokens > 0 && (
                <span className="text-cyan-400 text-[10px] font-semibold bg-cyan-950/80 border border-cyan-800/60 px-1.5 py-0.5 rounded ml-1">
                  ⚡ {trace.token_usage.cached_tokens.toLocaleString()} cached
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-800/80">
          <button
            onClick={() => handleTabSelect('output')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'output'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Output</span>
          </button>

          <button
            onClick={() => handleTabSelect('prompts')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'prompts'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Prompts (System & User)</span>
          </button>

          <button
            onClick={() => handleTabSelect('diff')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'diff'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Diff Comparison</span>
          </button>

          <button
            onClick={() => handleTabSelect('analytics')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'analytics'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Token & Latency Analytics</span>
          </button>

          <button
            onClick={() => handleTabSelect('raw')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ml-auto ${
              activeTab === 'raw'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>Raw Trace JSON</span>
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
          <div className="h-full bg-slate-900/60 border border-slate-800 rounded-xl p-4 overflow-y-auto font-mono text-xs text-indigo-300">
            <pre>{JSON.stringify(trace, null, 2)}</pre>
          </div>
        )}
      </div>
    </main>
  );
};
