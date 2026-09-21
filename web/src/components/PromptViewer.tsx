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
        <mark key={i} className="bg-[#d9a05b] text-[#2b2622] font-semibold px-0.5 rounded-[2px]">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="flex flex-col h-full space-y-3 font-sans">
      {/* Subtab navigation & Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-[#3f3a36]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-0.5 bg-[#24201d] p-0.5 rounded-[3px] border border-[#3f3a36]">
            <button
              onClick={() => setActiveSubTab('both')}
              className={`px-2.5 py-1 rounded-[2px] text-xs font-medium transition-colors ${
                activeSubTab === 'both'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold shadow-xs'
                  : 'text-[#b0a89f] hover:text-[#f7f5f0]'
              }`}
            >
              Split View
            </button>
            <button
              onClick={() => setActiveSubTab('system')}
              className={`px-2.5 py-1 rounded-[2px] text-xs font-medium transition-colors ${
                activeSubTab === 'system'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold shadow-xs'
                  : 'text-[#b0a89f] hover:text-[#f7f5f0]'
              }`}
            >
              System Prompt Only
            </button>
            <button
              onClick={() => setActiveSubTab('user')}
              className={`px-2.5 py-1 rounded-[2px] text-xs font-medium transition-colors ${
                activeSubTab === 'user'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold shadow-xs'
                  : 'text-[#b0a89f] hover:text-[#f7f5f0]'
              }`}
            >
              User Prompt Only
            </button>
          </div>

          {/* Total input tokens badge */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] bg-[#383330] border border-[#3f3a36] text-xs font-mono">
            <Cpu className="w-3.5 h-3.5 text-[#b0a89f]" />
            <span className="text-[#857d75]">Total Input:</span>
            <span className="font-bold text-[#f7f5f0]">
              {tokenStats.totalTokens.toLocaleString()} tok
            </span>
            <span className="text-[10px] text-[#857d75] font-medium">
              {tokenStats.isMeasured ? '(Measured)' : '(Est.)'}
            </span>
          </div>
        </div>

        {/* Find in prompts */}
        <div className="relative w-64">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#857d75]" />
          <input
            type="text"
            placeholder="Highlight terms..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="w-full pl-8 pr-2.5 py-1 bg-[#24201d] border border-[#3f3a36] rounded-[3px] text-xs text-[#f7f5f0] placeholder-[#857d75] focus:outline-none focus:border-[#b0a89f] font-mono"
          />
        </div>
      </div>

      {/* Prompts container */}
      <div className={`flex-1 grid gap-3 overflow-y-auto ${activeSubTab === 'both' ? 'lg:grid-cols-2' : 'grid-cols-1'}`}>
        
        {/* System Prompt Block */}
        {(activeSubTab === 'both' || activeSubTab === 'system') && (
          <div className="flex flex-col bg-[#24201d] border border-[#3f3a36] rounded-[4px] overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-[#2b2622] border-b border-[#3f3a36]">
              <div className="flex items-center gap-2">
                <Terminal className="w-3.5 h-3.5 text-[#b0a89f]" />
                <span className="text-xs font-bold text-[#f7f5f0] tracking-wide font-mono uppercase">
                  System Instruction
                </span>
                <span className="text-[10px] font-mono text-[#d9a05b] bg-[#383330] border border-[#3f3a36] px-1.5 py-0.2 rounded-[2px]">
                  ~{tokenStats.systemTokens.toLocaleString()} tok
                </span>
                <span className="text-[11px] text-[#857d75] font-mono">
                  ({trace.system_prompt.length.toLocaleString()} chars)
                </span>
              </div>
              <button
                onClick={() => handleCopy(trace.system_prompt, true)}
                className="flex items-center gap-1 text-xs text-[#b0a89f] hover:text-[#f7f5f0] px-2 py-0.5 rounded-[2px] hover:bg-[#383330] transition-colors font-mono"
                title="Copy system prompt"
              >
                {copiedSystem ? <Check className="w-3.5 h-3.5 text-[#7fa678]" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedSystem ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto bg-[#24201d] font-mono text-xs text-[#b0a89f] leading-relaxed whitespace-pre-wrap selection:bg-[#383330] selection:text-[#f7f5f0]">
              {highlightMatches(trace.system_prompt)}
            </div>
          </div>
        )}

        {/* User Prompt Block */}
        {(activeSubTab === 'both' || activeSubTab === 'user') && (
          <div className="flex flex-col bg-[#24201d] border border-[#3f3a36] rounded-[4px] overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-[#2b2622] border-b border-[#3f3a36]">
              <div className="flex items-center gap-2">
                <User className="w-3.5 h-3.5 text-[#b0a89f]" />
                <span className="text-xs font-bold text-[#f7f5f0] tracking-wide font-mono uppercase">
                  User Context / Excerpt
                </span>
                <span className="text-[10px] font-mono text-[#8b9bb4] bg-[#383330] border border-[#3f3a36] px-1.5 py-0.2 rounded-[2px]">
                  ~{tokenStats.userTokens.toLocaleString()} tok
                </span>
                <span className="text-[11px] text-[#857d75] font-mono">
                  ({trace.user_prompt.length.toLocaleString()} chars)
                </span>
              </div>
              <button
                onClick={() => handleCopy(trace.user_prompt, false)}
                className="flex items-center gap-1 text-xs text-[#b0a89f] hover:text-[#f7f5f0] px-2 py-0.5 rounded-[2px] hover:bg-[#383330] transition-colors font-mono"
                title="Copy user prompt"
              >
                {copiedUser ? <Check className="w-3.5 h-3.5 text-[#7fa678]" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedUser ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto bg-[#24201d] font-mono text-xs text-[#b0a89f] leading-relaxed whitespace-pre-wrap selection:bg-[#383330] selection:text-[#f7f5f0]">
              {highlightMatches(trace.user_prompt)}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
