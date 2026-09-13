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
    <div className="flex flex-col h-full space-y-4">
      {/* Diff Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          {/* Source selection */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-400 font-medium">From:</span>
            <select
              value={sourceTraceId}
              onChange={(e) => setSourceTraceId(e.target.value)}
              aria-label="Select source trace for diff"
              className="bg-slate-950 border border-slate-800 rounded-md px-2.5 py-1 text-xs text-slate-200"
            >
              {allTraces.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {t.agent} ({t.stage})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />

          {/* Target selection */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-400 font-medium">To:</span>
            <select
              value={targetTraceId}
              onChange={(e) => setTargetTraceId(e.target.value)}
              aria-label="Select target trace for diff"
              className="bg-slate-950 border border-slate-800 rounded-md px-2.5 py-1 text-xs text-slate-200"
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
        <div className="flex items-center gap-3 text-xs">
          <span className="text-emerald-400 font-semibold bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
            +{additions} words
          </span>
          <span className="text-red-400 font-semibold bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded">
            -{deletions} words
          </span>

          {/* View mode toggle */}
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setDiffMode('inline')}
              className={`p-1 rounded ${diffMode === 'inline' ? 'bg-indigo-600 text-white' : 'text-slate-400'}`}
              title="Inline Unified Diff"
            >
              <AlignJustify className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setDiffMode('split')}
              className={`p-1 rounded ${diffMode === 'split' ? 'bg-indigo-600 text-white' : 'text-slate-400'}`}
              title="Side-by-Side Diff"
            >
              <Columns className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Granularity */}
          <button
            onClick={() => setGranularity(granularity === 'words' ? 'lines' : 'words')}
            className="text-[11px] px-2 py-1 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded border border-slate-700"
          >
            By {granularity}
          </button>
        </div>
      </div>

      {/* Diff Rendering Body */}
      <div className="flex-1 overflow-y-auto">
        {diffMode === 'inline' ? (
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 font-serif-prose text-slate-200 text-base leading-loose whitespace-pre-wrap">
            {diffParts.map((part, index) => {
              if (part.added) {
                return (
                  <span
                    key={index}
                    className="bg-emerald-500/20 text-emerald-300 border-b-2 border-emerald-500 px-1 py-0.5 rounded font-medium"
                  >
                    {part.value}
                  </span>
                );
              }
              if (part.removed) {
                return (
                  <span
                    key={index}
                    className="bg-red-500/20 text-red-400 line-through opacity-70 px-1 py-0.5 rounded"
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
          <div className="grid lg:grid-cols-2 gap-4 h-full">
            {/* Left side: Source */}
            <div className="flex flex-col bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-slate-850 border-b border-slate-800 text-xs font-semibold text-slate-300">
                Original Draft: {sourceTrace?.agent} ({sourceTrace?.stage})
              </div>
              <div className="p-4 overflow-y-auto font-serif-prose text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                {textA || '<Empty>'}
              </div>
            </div>

            {/* Right side: Target */}
            <div className="flex flex-col bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-slate-850 border-b border-slate-800 text-xs font-semibold text-slate-300">
                Polished Output: {targetTrace?.agent} ({targetTrace?.stage})
              </div>
              <div className="p-4 overflow-y-auto font-serif-prose text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                {textB || '<Empty>'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
