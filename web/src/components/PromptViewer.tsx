import React, { useState } from 'react';
import { AgentPromptTrace } from '../types/trace';
import { getPromptTokenStats } from '../utils/tokenEstimator';
import { Copy, Check, Terminal, User, Search, Cpu } from 'lucide-react';

interface PromptViewerProps {
  trace: AgentPromptTrace;
}

export const PromptViewer: React.FC<PromptViewerProps> = ({ trace }) => {
  const [activeSubTab, setActiveSubTab] = useState<'both' | 'system' | 'user'>('both');
  const [copiedSystem, setCopiedSystem] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [filterText, setFilterText] = useState('');

  const tokenStats = getPromptTokenStats(
    trace.system_prompt,
    trace.user_prompt,
    trace.token_usage?.input_tokens
  );

  const handleCopy = (text: string, isSystem: boolean) => {
    navigator.clipboard.writeText(text);
    if (isSystem) {
      setCopiedSystem(true);
      setTimeout(() => setCopiedSystem(false), 2000);
    } else {
      setCopiedUser(true);
      setTimeout(() => setCopiedUser(false), 2000);
    }
  };

  const highlightMatches = (content: string) => {
    if (!filterText.trim()) return content;
    const parts = content.split(new RegExp(`(${filterText})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === filterText.toLowerCase() ? (
        <mark key={i} className="bg-amber-400 text-slate-950 font-semibold px-0.5 rounded">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Subtab navigation & Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveSubTab('both')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeSubTab === 'both' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Split View
            </button>
            <button
              onClick={() => setActiveSubTab('system')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeSubTab === 'system' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              System Prompt Only
            </button>
            <button
              onClick={() => setActiveSubTab('user')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeSubTab === 'user' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              User Prompt Only
            </button>
          </div>

          {/* Total input tokens badge */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-slate-400">Total Input:</span>
            <span className="font-bold text-slate-100">
              {tokenStats.totalTokens.toLocaleString()} tokens
            </span>
            <span className="text-[10px] text-slate-500 font-medium">
              {tokenStats.isMeasured ? '(Measured)' : '(Est.)'}
            </span>
          </div>
        </div>

        {/* Find in prompts */}
        <div className="relative w-64">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-slate-400" />
          <input
            type="text"
            placeholder="Highlight words..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="w-full pl-8 pr-2 py-1 bg-slate-950 border border-slate-800 rounded-md text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Prompts container */}
      <div className={`flex-1 grid gap-4 overflow-y-auto ${activeSubTab === 'both' ? 'lg:grid-cols-2' : 'grid-cols-1'}`}>
        
        {/* System Prompt Block */}
        {(activeSubTab === 'both' || activeSubTab === 'system') && (
          <div className="flex flex-col bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-slate-850 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  System Instruction
                </span>
                <span className="text-[11px] font-medium text-purple-300 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full">
                  ~{tokenStats.systemTokens.toLocaleString()} tokens
                </span>
                <span className="text-[11px] text-slate-400">
                  ({trace.system_prompt.length.toLocaleString()} chars)
                </span>
              </div>
              <button
                onClick={() => handleCopy(trace.system_prompt, true)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-750 transition-colors"
                title="Copy system prompt"
              >
                {copiedSystem ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedSystem ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto bg-slate-950/70 font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap selection:bg-purple-900 selection:text-purple-100">
              {highlightMatches(trace.system_prompt)}
            </div>
          </div>
        )}

        {/* User Prompt Block */}
        {(activeSubTab === 'both' || activeSubTab === 'user') && (
          <div className="flex flex-col bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-slate-850 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  User Context / Excerpt
                </span>
                <span className="text-[11px] font-medium text-blue-300 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded-full">
                  ~{tokenStats.userTokens.toLocaleString()} tokens
                </span>
                <span className="text-[11px] text-slate-400">
                  ({trace.user_prompt.length.toLocaleString()} chars)
                </span>
              </div>
              <button
                onClick={() => handleCopy(trace.user_prompt, false)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-750 transition-colors"
                title="Copy user prompt"
              >
                {copiedUser ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedUser ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto bg-slate-950/70 font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap selection:bg-blue-900 selection:text-blue-100">
              {highlightMatches(trace.user_prompt)}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
