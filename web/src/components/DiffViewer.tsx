import React, { useState, useMemo } from 'react';
import { AgentPromptTrace } from '../types/trace';
import * as Diff from 'diff';
import { Columns, AlignJustify, ArrowRight, GitCompare } from 'lucide-react';

interface DiffViewerProps {
  currentTrace: AgentPromptTrace;
  allTraces: AgentPromptTrace[];
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ currentTrace, allTraces }) => {
  // Filter candidate traces: strictly drafting and polishing prose
  const draftingTraces = useMemo(
    () => allTraces.filter((t) => t.stage?.toLowerCase() === 'drafting'),
    [allTraces]
  );
  const polishingTraces = useMemo(
    () => allTraces.filter((t) => t.stage?.toLowerCase() === 'polishing'),
    [allTraces]
  );

  const getTraceLabel = (t?: AgentPromptTrace) => {
    if (!t) return 'None';
    const isDraft = t.stage?.toLowerCase() === 'drafting';
    const tag = isDraft ? 'Draft' : 'Polished';
    const parts: string[] = [];
    if (t.iteration && t.iteration > 1) {
      parts.push(`Pass ${t.iteration}`);
    }
    if (t.total_chunks && t.total_chunks > 1) {
      parts.push(`Chunk ${t.chunk_index + 1}/${t.total_chunks}`);
    }
    const details = parts.length > 0 ? ` (${parts.join(', ')})` : '';
    return `${tag}${details} - ${t.agent || t.model}`;
  };

  // Source candidates: drafting traces, plus earlier polishing passes if multiple exist
  const sourceCandidates = useMemo(() => {
    if (polishingTraces.length > 1) {
      return [...draftingTraces, ...polishingTraces.slice(0, -1)];
    }
    return draftingTraces;
  }, [draftingTraces, polishingTraces]);

  // Target candidates: polishing traces
  const targetCandidates = polishingTraces;

  // Initial source and target selection
  const initialPair = useMemo(() => {
    let src = draftingTraces[0]?.trace_id || '';
    let tgt = polishingTraces[polishingTraces.length - 1]?.trace_id || '';

    if (currentTrace.stage?.toLowerCase() === 'drafting') {
      src = currentTrace.trace_id;
      const match = polishingTraces.find((p) => p.chunk_index === currentTrace.chunk_index) ||
                    polishingTraces[polishingTraces.length - 1];
      if (match) tgt = match.trace_id;
    } else if (currentTrace.stage?.toLowerCase() === 'polishing') {
      tgt = currentTrace.trace_id;
      const match = draftingTraces.find((d) => d.chunk_index === currentTrace.chunk_index) ||
                    draftingTraces[0];
      if (match) src = match.trace_id;
    }

    return { src, tgt };
  }, [currentTrace, draftingTraces, polishingTraces]);

  const [sourceTraceId, setSourceTraceId] = useState<string>(initialPair.src);
  const [targetTraceId, setTargetTraceId] = useState<string>(initialPair.tgt);
  const [diffMode, setDiffMode] = useState<'inline' | 'split'>('inline');
  const [granularity, setGranularity] = useState<'words' | 'lines'>('words');

  // If no drafting or polishing trace is available yet, render clean informative state
  if (draftingTraces.length === 0 || polishingTraces.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-80 text-center p-8 bg-[#24201d] border border-[#3f3a36] rounded-[4px]">
        <GitCompare className="w-12 h-12 text-[#857d75] mb-3 opacity-60" />
        <h3 className="text-sm font-semibold text-[#f7f5f0] mb-1 font-mono">
          Diff Comparison Unavailable
        </h3>
        <p className="text-xs text-[#aea69c] max-w-md leading-relaxed">
          Diff Comparison strictly compares raw translation draft prose against polished prose.
          {draftingTraces.length === 0
            ? " The drafting stage has not completed yet for this chapter."
            : " The polishing stage has not completed yet for this chapter."}
        </p>
      </div>
    );
  }

  const sourceTrace =
    sourceCandidates.find((t) => t.trace_id === sourceTraceId) ||
    draftingTraces[0];
  const targetTrace =
    targetCandidates.find((t) => t.trace_id === targetTraceId) ||
    polishingTraces[polishingTraces.length - 1];

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
              value={sourceTrace?.trace_id || sourceTraceId}
              onChange={(e) => setSourceTraceId(e.target.value)}
              aria-label="Select source trace for diff"
              className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2 py-1 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] font-mono"
            >
              {sourceCandidates.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {getTraceLabel(t)}
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-3.5 h-3.5 text-[#857d75]" />

          {/* Target selection */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-[#857d75] font-mono">To:</span>
            <select
              value={targetTrace?.trace_id || targetTraceId}
              onChange={(e) => setTargetTraceId(e.target.value)}
              aria-label="Select target trace for diff"
              className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2 py-1 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] font-mono"
            >
              {targetCandidates.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {getTraceLabel(t)}
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
                Original Draft: {getTraceLabel(sourceTrace)}
              </div>
              <div className="p-4 overflow-y-auto font-serif text-[#b0a89f] text-sm leading-relaxed whitespace-pre-wrap">
                {textA || '<Empty>'}
              </div>
            </div>

            {/* Right side: Target */}
            <div className="flex flex-col bg-[#24201d] border border-[#3f3a36] rounded-[4px] overflow-hidden">
              <div className="px-3 py-2 bg-[#2b2622] border-b border-[#3f3a36] text-xs font-semibold text-[#f7f5f0] font-mono">
                Polished Output: {getTraceLabel(targetTrace)}
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
