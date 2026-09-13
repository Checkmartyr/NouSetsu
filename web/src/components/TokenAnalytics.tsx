import React from 'react';
import { AgentPromptTrace, ChapterTraceDocument } from '../types/trace';
import { Cpu, Zap, PieChart, Layers, BarChart2 } from 'lucide-react';

interface TokenAnalyticsProps {
  currentTrace: AgentPromptTrace;
  chapterDoc: ChapterTraceDocument;
}

// Map pipeline stage to literary German agent designations and badges
const STAGE_AGENT_INFO: Record<
  string,
  { codename: string; role: string; color: string; border: string; bg: string }
> = {
  extraction: {
    codename: 'Schriftdetektiv',
    role: 'Entity Detective',
    color: 'text-amber-400',
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/10',
  },
  drafting: {
    codename: 'Wortschmied',
    role: 'Wordsmith',
    color: 'text-blue-400',
    border: 'border-blue-500/30',
    bg: 'bg-blue-500/10',
  },
  critique: {
    codename: 'Zensor',
    role: 'Inspector',
    color: 'text-purple-400',
    border: 'border-purple-500/30',
    bg: 'bg-purple-500/10',
  },
  polishing: {
    codename: 'Feinschliff',
    role: 'Prose Stylist',
    color: 'text-emerald-400',
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-500/10',
  },
  chronicling: {
    codename: 'Chronist',
    role: 'Memory Keeper',
    color: 'text-rose-400',
    border: 'border-rose-500/30',
    bg: 'bg-rose-500/10',
  },
};

interface AggregatedStageMetrics {
  stage: string;
  agent: string;
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  thoughtTokens: number;
  totalTokens: number;
  durationSeconds: number;
  interactionCount: number;
}

export const TokenAnalytics: React.FC<TokenAnalyticsProps> = ({ currentTrace, chapterDoc }) => {
  const chTokens = chapterDoc.total_token_usage || {
    input_tokens: 0,
    output_tokens: 0,
    thought_tokens: 0,
    cached_tokens: 0,
    total_tokens: 0,
  };

  const trTokens = currentTrace.token_usage || {
    input_tokens: 0,
    output_tokens: 0,
    thought_tokens: 0,
    cached_tokens: 0,
    total_tokens: 0,
  };

  // Compute tokens per second
  const chTps =
    chapterDoc.total_duration_seconds > 0
      ? Math.round(chTokens.total_tokens / chapterDoc.total_duration_seconds)
      : 0;

  const trTps =
    currentTrace.duration_seconds > 0
      ? Math.round(trTokens.total_tokens / currentTrace.duration_seconds)
      : 0;

  // Chapter-level cache hit rate
  const cacheHitRate =
    chTokens.input_tokens > 0
      ? Math.round((chTokens.cached_tokens / chTokens.input_tokens) * 100)
      : 0;

  // Trace-level cache hit rate
  const trCacheHitRate =
    trTokens.input_tokens > 0
      ? Math.round((trTokens.cached_tokens / trTokens.input_tokens) * 100)
      : 0;

  // Canonical stages ordering
  const canonicalStages = ['extraction', 'drafting', 'critique', 'polishing', 'chronicling'];

  // Stages detailed token aggregation
  const stageMetricsMap: Record<string, AggregatedStageMetrics> = {};

  chapterDoc.traces.forEach((t) => {
    const st = t.stage || 'unknown';
    if (!stageMetricsMap[st]) {
      stageMetricsMap[st] = {
        stage: st,
        agent: t.agent || st,
        inputTokens: 0,
        cachedTokens: 0,
        outputTokens: 0,
        thoughtTokens: 0,
        totalTokens: 0,
        durationSeconds: 0,
        interactionCount: 0,
      };
    }
    const sm = stageMetricsMap[st];
    sm.interactionCount += 1;
    sm.durationSeconds += t.duration_seconds || 0;
    if (t.token_usage) {
      sm.inputTokens += t.token_usage.input_tokens || 0;
      sm.cachedTokens += t.token_usage.cached_tokens || 0;
      sm.outputTokens += t.token_usage.output_tokens || 0;
      sm.thoughtTokens += t.token_usage.thought_tokens || 0;
      sm.totalTokens += t.token_usage.total_tokens || 0;
    }
  });

  const stageEntries = Object.values(stageMetricsMap).sort((a, b) => {
    const idxA = canonicalStages.indexOf(a.stage);
    const idxB = canonicalStages.indexOf(b.stage);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return a.stage.localeCompare(b.stage);
  });

  return (
    <div className="space-y-6 overflow-y-auto max-h-full pr-2">
      {/* Chapter Overview Cards */}
      <div>
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span>Chapter-Wide Performance & Token Allocation</span>
        </h4>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {/* Total Tokens */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" />
              <span>Total Tokens</span>
            </div>
            <div className="text-xl font-bold text-slate-100">
              {chTokens.total_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              across {chapterDoc.total_interactions} interactions
            </div>
          </div>

          {/* Input Tokens */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span>Input Tokens</span>
            </div>
            <div className="text-xl font-bold text-blue-400">
              {chTokens.input_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.input_tokens / chTokens.total_tokens) * 100) : 0}% of chapter
            </div>
          </div>

          {/* Cached Tokens (KV Cache) */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 relative overflow-hidden">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-cyan-300 font-medium">Cached Tokens</span>
              </div>
              <span className="text-[10px] font-semibold text-cyan-400 bg-cyan-950/80 border border-cyan-800/60 px-1.5 py-0.5 rounded">
                ⚡ KV Hit
              </span>
            </div>
            <div className="text-xl font-bold text-cyan-300">
              {chTokens.cached_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-cyan-500 mt-1">
              {cacheHitRate}% cache hit rate
            </div>
          </div>

          {/* Output Tokens */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Output Tokens</span>
            </div>
            <div className="text-xl font-bold text-emerald-400">
              {chTokens.output_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.output_tokens / chTokens.total_tokens) * 100) : 0}% of chapter
            </div>
          </div>

          {/* Latency & Speed */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Throughput</span>
            </div>
            <div className="text-xl font-bold text-slate-100">
              {chTps.toLocaleString()} <span className="text-xs text-slate-400 font-normal">tok/s</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {chapterDoc.total_duration_seconds.toFixed(1)}s total runtime
            </div>
          </div>
        </div>
      </div>

      {/* Stage Breakdown Bar */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800/80">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-semibold text-slate-200">Stage Token Distribution</span>
            <span className="text-[11px] text-slate-500">(Input · Cached · Output per Agent)</span>
          </div>

          {/* Color Legend */}
          <div className="flex items-center gap-3 text-[11px] text-slate-400">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-blue-500"></span>
              <span>Input</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-cyan-400"></span>
              <span className="text-cyan-300 font-medium flex items-center gap-0.5">
                ⚡ Cached
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-purple-500"></span>
              <span>Thought</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500"></span>
              <span>Output</span>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {stageEntries.map((sm) => {
            const info = STAGE_AGENT_INFO[sm.stage] || {
              codename: sm.agent,
              role: 'Agent',
              color: 'text-slate-300',
              border: 'border-slate-700',
              bg: 'bg-slate-800',
            };

            const freshInput = Math.max(0, sm.inputTokens - sm.cachedTokens);
            const cached = sm.cachedTokens;
            const thought = sm.thoughtTokens;
            const output = sm.outputTokens;
            const total = freshInput + cached + thought + output || sm.totalTokens || 1;

            const freshPct = (freshInput / total) * 100;
            const cachedPct = (cached / total) * 100;
            const thoughtPct = (thought / total) * 100;
            const outputPct = (output / total) * 100;

            const stageChapterPct =
              chTokens.total_tokens > 0 ? Math.round((sm.totalTokens / chTokens.total_tokens) * 100) : 0;
            const stageCacheHitRate =
              sm.inputTokens > 0 ? Math.round((sm.cachedTokens / sm.inputTokens) * 100) : 0;

            return (
              <div key={sm.stage} className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                {/* Stage Header */}
                <div className="flex flex-wrap items-center justify-between text-xs gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${info.bg} ${info.border} ${info.color}`}>
                      {info.codename}
                    </span>
                    <span className="capitalize font-semibold text-slate-200">
                      {sm.stage}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      ({info.role})
                    </span>
                    {sm.interactionCount > 1 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                        {sm.interactionCount} calls
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="text-slate-400">{sm.durationSeconds.toFixed(1)}s</span>
                    <span className="font-semibold text-slate-200">
                      {sm.totalTokens.toLocaleString()} tok
                      <span className="text-slate-500 font-normal ml-1">({stageChapterPct}% of chapter)</span>
                    </span>
                  </div>
                </div>

                {/* Multi-Segment Stacked Bar */}
                <div className="w-full bg-slate-900 rounded-full h-3 overflow-hidden flex shadow-inner">
                  {freshPct > 0 && (
                    <div
                      className="h-full bg-blue-500 hover:brightness-110 transition-all"
                      style={{ width: `${freshPct}%` }}
                      title={`Input (Uncached): ${freshInput.toLocaleString()} tok (${freshPct.toFixed(1)}%)`}
                    />
                  )}
                  {cachedPct > 0 && (
                    <div
                      className="h-full bg-cyan-400 hover:brightness-110 transition-all relative overflow-hidden"
                      style={{ width: `${cachedPct}%` }}
                      title={`Cached KV Tokens: ${cached.toLocaleString()} tok (${cachedPct.toFixed(1)}% of stage, ${stageCacheHitRate}% cache hit)`}
                    />
                  )}
                  {thoughtPct > 0 && (
                    <div
                      className="h-full bg-purple-500 hover:brightness-110 transition-all"
                      style={{ width: `${thoughtPct}%` }}
                      title={`Thought / Reasoning: ${thought.toLocaleString()} tok (${thoughtPct.toFixed(1)}%)`}
                    />
                  )}
                  {outputPct > 0 && (
                    <div
                      className="h-full bg-emerald-500 hover:brightness-110 transition-all"
                      style={{ width: `${outputPct}%` }}
                      title={`Output: ${output.toLocaleString()} tok (${outputPct.toFixed(1)}%)`}
                    />
                  )}
                </div>

                {/* Token Category Breakdown Chips */}
                <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px]">
                  {/* Input */}
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                    <span>Input:</span>
                    <span className="font-mono font-semibold text-blue-200">{sm.inputTokens.toLocaleString()}</span>
                  </div>

                  {/* Cached */}
                  <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md border ${
                    sm.cachedTokens > 0
                      ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-200 shadow-sm shadow-cyan-500/10'
                      : 'bg-slate-900 border-slate-800 text-slate-500'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${sm.cachedTokens > 0 ? 'bg-cyan-400 animate-pulse' : 'bg-slate-600'}`}></span>
                    <span className="flex items-center gap-0.5">
                      ⚡ Cached:
                    </span>
                    <span className="font-mono font-semibold">{sm.cachedTokens.toLocaleString()}</span>
                    {sm.cachedTokens > 0 && (
                      <span className="text-[10px] text-cyan-400/90 font-medium">({stageCacheHitRate}% hit)</span>
                    )}
                  </div>

                  {/* Thought (only if present) */}
                  {sm.thoughtTokens > 0 && (
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                      <span>Thought:</span>
                      <span className="font-mono font-semibold text-purple-200">{sm.thoughtTokens.toLocaleString()}</span>
                    </div>
                  )}

                  {/* Output */}
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                    <span>Output:</span>
                    <span className="font-mono font-semibold text-emerald-200">{sm.outputTokens.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current Interaction Detail Gauge */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
        <h5 className="text-xs font-semibold text-slate-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <PieChart className="w-4 h-4 text-emerald-400" />
            Selected Interaction: {currentTrace.agent} ({currentTrace.stage})
          </span>
          <div className="flex items-center gap-2">
            {trTokens.cached_tokens > 0 && (
              <span className="text-[10px] font-semibold text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-2 py-0.5 rounded-full flex items-center gap-1">
                ⚡ {trCacheHitRate}% Cache Hit
              </span>
            )}
            <span className="text-[11px] text-slate-400">{trTokens.total_tokens.toLocaleString()} Total Tokens</span>
          </div>
        </h5>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 text-xs">
          {/* Input */}
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>Input Tokens</span>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
            </div>
            <div className="text-base font-bold text-blue-400 mt-0.5">
              {trTokens.input_tokens.toLocaleString()}
            </div>
          </div>

          {/* Cached */}
          <div className={`p-2.5 rounded-lg border ${
            trTokens.cached_tokens > 0
              ? 'bg-cyan-950/30 border-cyan-500/30 text-cyan-300'
              : 'bg-slate-950 border-slate-800 text-slate-400'
          }`}>
            <div className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-1 text-cyan-400 font-medium">
                ⚡ Cached
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
            </div>
            <div className="text-base font-bold text-cyan-300 mt-0.5">
              {trTokens.cached_tokens.toLocaleString()}
            </div>
          </div>

          {/* Output */}
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>Output Tokens</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            </div>
            <div className="text-base font-bold text-emerald-400 mt-0.5">
              {trTokens.output_tokens.toLocaleString()}
            </div>
          </div>

          {/* Thought */}
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>Thought Tokens</span>
              <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
            </div>
            <div className="text-base font-bold text-purple-400 mt-0.5">
              {trTokens.thought_tokens.toLocaleString()}
            </div>
          </div>

          {/* Duration & Speed */}
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <div className="flex items-center justify-between text-slate-400 text-[11px]">
              <span>Duration</span>
              <Zap className="w-3 h-3 text-amber-400" />
            </div>
            <div className="text-base font-bold text-amber-400 mt-0.5">
              {currentTrace.duration_seconds.toFixed(2)}s
              <span className="text-[10px] text-slate-400 font-normal ml-1">({trTps} t/s)</span>
            </div>
          </div>
        </div>

        {/* Selected Interaction Stacked Bar */}
        {trTokens.total_tokens > 0 && (
          <div className="pt-1">
            {(() => {
              const trFresh = Math.max(0, trTokens.input_tokens - trTokens.cached_tokens);
              const trCached = trTokens.cached_tokens;
              const trThought = trTokens.thought_tokens;
              const trOutput = trTokens.output_tokens;
              const trTot = trFresh + trCached + trThought + trOutput || trTokens.total_tokens || 1;

              const trFreshPct = (trFresh / trTot) * 100;
              const trCachedPct = (trCached / trTot) * 100;
              const trThoughtPct = (trThought / trTot) * 100;
              const trOutputPct = (trOutput / trTot) * 100;

              return (
                <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden flex shadow-inner">
                  {trFreshPct > 0 && (
                    <div className="h-full bg-blue-500" style={{ width: `${trFreshPct}%` }} title={`Input: ${trFresh.toLocaleString()}`} />
                  )}
                  {trCachedPct > 0 && (
                    <div className="h-full bg-cyan-400" style={{ width: `${trCachedPct}%` }} title={`Cached: ${trCached.toLocaleString()}`} />
                  )}
                  {trThoughtPct > 0 && (
                    <div className="h-full bg-purple-500" style={{ width: `${trThoughtPct}%` }} title={`Thought: ${trThought.toLocaleString()}`} />
                  )}
                  {trOutputPct > 0 && (
                    <div className="h-full bg-emerald-500" style={{ width: `${trOutputPct}%` }} title={`Output: ${trOutput.toLocaleString()}`} />
                  )}
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
};
