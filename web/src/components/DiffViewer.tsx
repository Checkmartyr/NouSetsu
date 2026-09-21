import React, { useState } from 'react';
import { AgentPromptTrace } from '../types/trace';
import * as Diff from 'diff';
import { Columns, AlignJustify, ArrowRight } from 'lucide-react';

interface DiffViewerProps {
  currentTrace: AgentPromptTrace;
  allTraces: AgentPromptTrace[];
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ currentTrace, allTraces }) => {
  // Find standard candidate targets
  const drafterTrace = allTraces.find((t) => t.stage === 'drafting');
  const polisherTrace = allTraces.find((t) => t.stage === 'polishing');

  // Initial source and target selection
  const defaultSourceId = drafterTrace ? drafterTrace.trace_id : allTraces[0]?.trace_id;
  const defaultTargetId = polisherTrace
    ? polisherTrace.trace_id
    : currentTrace.trace_id !== defaultSourceId
    ? currentTrace.trace_id
    : allTraces[1]?.trace_id || allTraces[0]?.trace_id;

  const [sourceTraceId, setSourceTraceId] = useState<string>(defaultSourceId || '');
  const [targetTraceId, setTargetTraceId] = useState<string>(defaultTargetId || '');
  const [diffMode, setDiffMode] = useState<'inline' | 'split'>('inline');
  const [granularity, setGranularity] = useState<'words' | 'lines'>('words');

  const sourceTrace = allTraces.find((t) => t.trace_id === sourceTraceId);
  const targetTrace = allTraces.find((t) => t.trace_id === targetTraceId);

  const textA = sourceTrace?.raw_output || '';
  const textB = targetTrace?.raw_output || '';

  // Calculate diff
  const diffParts =
    granularity === 'words' ? Diff.diffWords(textA, textB) : Diff.diffLines(textA, textB);

  let additions = 0;
  let deletions = 0;
  diffParts.forEach((p) => {
    if (p.added) additions += p.value.split(/\s+/).filter(Boolean).length;
    if (p.removed) deletions += p.value.split(/\s+/).filter(Boolean).length;
  });

  return (
    <div className="flex flex-col h-full space-y-3 font-sans">
      {/* Diff Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-[#3f3a36]">
        <div className="flex items-center gap-3">
          {/* Source selection */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-[#857d75] font-mono">From:</span>
            <select
              value={sourceTraceId}
              onChange={(e) => setSourceTraceId(e.target.value)}
              aria-label="Select source trace for diff"
              className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2 py-1 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] font-mono"
            >
              {allTraces.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {t.agent} ({t.stage})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-3.5 h-3.5 text-[#857d75]" />

          {/* Target selection */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-[#857d75] font-mono">To:</span>
            <select
              value={targetTraceId}
              onChange={(e) => setTargetTraceId(e.target.value)}
              aria-label="Select target trace for diff"
              className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2 py-1 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] font-mono"
            >
              {allTraces.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {t.agent} ({t.stage})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Change stats */}
        <div className="flex items-center gap-2.5 text-xs font-mono">
          <span className="text-[#7fa678] font-semibold bg-[#272f26] border border-[#7fa678]/40 px-2 py-0.5 rounded-[2px]">
            +{additions} words
          </span>
          <span className="text-[#cf6659] font-semibold bg-[#382522] border border-[#cf6659]/40 px-2 py-0.5 rounded-[2px]">
            -{deletions} words
          </span>

          {/* View mode toggle */}
          <div className="flex items-center gap-0.5 bg-[#24201d] p-0.5 rounded-[3px] border border-[#3f3a36]">
            <button
              onClick={() => setDiffMode('inline')}
              className={`p-1 rounded-[2px] transition-colors ${diffMode === 'inline' ? 'bg-[#f7f5f0] text-[#2b2622]' : 'text-[#857d75] hover:text-[#f7f5f0]'}`}
              title="Inline Unified Diff"
            >
              <AlignJustify className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setDiffMode('split')}
              className={`p-1 rounded-[2px] transition-colors ${diffMode === 'split' ? 'bg-[#f7f5f0] text-[#2b2622]' : 'text-[#857d75] hover:text-[#f7f5f0]'}`}
              title="Side-by-Side Diff"
            >
              <Columns className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Granularity */}
          <button
            onClick={() => setGranularity(granularity === 'words' ? 'lines' : 'words')}
            className="text-[11px] px-2 py-1 bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] rounded-[3px] border border-[#3f3a36] transition-colors font-mono"
          >
            By {granularity}
          </button>
        </div>
      </div>

      {/* Diff Rendering Body */}
      <div className="flex-1 overflow-y-auto">
        {diffMode === 'inline' ? (
          <div className="bg-[#24201d] border border-[#3f3a36] rounded-[4px] p-5 font-serif text-[#f7f5f0] text-base leading-loose whitespace-pre-wrap">
            {diffParts.map((part, index) => {
              if (part.added) {
                return (
                  <span
                    key={index}
                    className="bg-[#272f26] text-[#a5c49f] border-b border-[#7fa678] px-0.5 rounded-[2px] font-medium"
                  >
                    {part.value}
                  </span>
                );
              }
              if (part.removed) {
                return (
                  <span
                    key={index}
                    className="bg-[#382522] text-[#e67b73] line-through opacity-75 px-0.5 rounded-[2px]"
                  >
                    {part.value}
                  </span>
                );
              }
              return <span key={index}>{part.value}</span>;
            })}
          </div>
        ) : (
          /* Side by side view */
          <div className="grid lg:grid-cols-2 gap-3 h-full">
            {/* Left side: Source */}
            <div className="flex flex-col bg-[#24201d] border border-[#3f3a36] rounded-[4px] overflow-hidden">
              <div className="px-3 py-2 bg-[#2b2622] border-b border-[#3f3a36] text-xs font-semibold text-[#f7f5f0] font-mono">
                Original Draft: {sourceTrace?.agent} ({sourceTrace?.stage})
              </div>
              <div className="p-4 overflow-y-auto font-serif text-[#b0a89f] text-sm leading-relaxed whitespace-pre-wrap">
                {textA || '<Empty>'}
              </div>
            </div>

            {/* Right side: Target */}
            <div className="flex flex-col bg-[#24201d] border border-[#3f3a36] rounded-[4px] overflow-hidden">
              <div className="px-3 py-2 bg-[#2b2622] border-b border-[#3f3a36] text-xs font-semibold text-[#f7f5f0] font-mono">
                Polished Output: {targetTrace?.agent} ({targetTrace?.stage})
              </div>
              <div className="p-4 overflow-y-auto font-serif text-[#f7f5f0] text-sm leading-relaxed whitespace-pre-wrap">
                {textB || '<Empty>'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
