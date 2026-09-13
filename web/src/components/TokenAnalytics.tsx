import React from 'react';
import { AgentPromptTrace, ChapterTraceDocument } from '../types/trace';
import { Cpu, Zap, PieChart, Layers, BarChart2 } from 'lucide-react';

interface TokenAnalyticsProps {
  currentTrace: AgentPromptTrace;
  chapterDoc: ChapterTraceDocument;
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

  // Stages token aggregation
  const stageTokenMap: Record<string, number> = {};
  const stageDurationMap: Record<string, number> = {};

  chapterDoc.traces.forEach((t) => {
    stageTokenMap[t.stage] = (stageTokenMap[t.stage] || 0) + (t.token_usage?.total_tokens || 0);
    stageDurationMap[t.stage] = (stageDurationMap[t.stage] || 0) + (t.duration_seconds || 0);
  });

  return (
    <div className="space-y-6 overflow-y-auto max-h-full pr-2">
      {/* Chapter Overview Cards */}
      <div>
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span>Chapter-Wide Performance & Token Allocation</span>
        </h4>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Total Tokens */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
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
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span>Input Tokens</span>
            </div>
            <div className="text-xl font-bold text-slate-100">
              {chTokens.input_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.input_tokens / chTokens.total_tokens) * 100) : 0}% of chapter
            </div>
          </div>

          {/* Output Tokens */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Output Tokens</span>
            </div>
            <div className="text-xl font-bold text-slate-100">
              {chTokens.output_tokens.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.output_tokens / chTokens.total_tokens) * 100) : 0}% of chapter
            </div>
          </div>

          {/* Latency & Speed */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
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
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
        <h5 className="text-xs font-semibold text-slate-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-purple-400" />
            Stage Token Distribution
          </span>
          <span className="text-[11px] text-slate-500">Tokens & Latency per Stage</span>
        </h5>

        <div className="space-y-2">
          {Object.entries(stageTokenMap).map(([stage, tokens]) => {
            const percent = chTokens.total_tokens > 0 ? Math.round((tokens / chTokens.total_tokens) * 100) : 0;
            const duration = stageDurationMap[stage] || 0;

            return (
              <div key={stage} className="space-y-1 text-xs">
                <div className="flex items-center justify-between text-slate-300">
                  <span className="capitalize font-medium">{stage}</span>
                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="text-slate-400">{duration.toFixed(1)}s</span>
                    <span className="font-semibold text-slate-200">{tokens.toLocaleString()} tok ({percent}%)</span>
                  </div>
                </div>
                <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(percent, 2)}%` }}
                  ></div>
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
          <span className="text-[11px] text-slate-500">{trTokens.total_tokens.toLocaleString()} Total Tokens</span>
        </h5>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 text-[11px]">Input Tokens</span>
            <div className="text-base font-bold text-blue-400 mt-0.5">
              {trTokens.input_tokens.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 text-[11px]">Output Tokens</span>
            <div className="text-base font-bold text-emerald-400 mt-0.5">
              {trTokens.output_tokens.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 text-[11px]">Thought Tokens</span>
            <div className="text-base font-bold text-purple-400 mt-0.5">
              {trTokens.thought_tokens.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 text-[11px]">Duration & Speed</span>
            <div className="text-base font-bold text-amber-400 mt-0.5">
              {currentTrace.duration_seconds.toFixed(2)}s
              <span className="text-[10px] text-slate-400 font-normal ml-1">({trTps} t/s)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
