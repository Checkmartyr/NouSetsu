import React from 'react';
import { AgentPromptTrace, ChapterTraceDocument } from '../types/trace';
import { Cpu, Zap, PieChart, Layers, BarChart2, Coins } from 'lucide-react';
import {
  calculateCost,
  formatCost,
  formatMicroCost,
  getModelPricing,
  ModelPricing,
  CostBreakdown,
} from '../utils/pricing';

interface TokenAnalyticsProps {
  currentTrace: AgentPromptTrace;
  chapterDoc: ChapterTraceDocument;
}

// Map pipeline stage to agent names, roles, and badges
const STAGE_AGENT_INFO: Record<
  string,
  { name: string; role: string; color: string; border: string; bg: string }
> = {
  extraction: {
    name: 'Entity Extractor',
    role: 'Entity Detective',
    color: 'text-[#d9a05b]',
    border: 'border-[#3f3a36]',
    bg: 'bg-[#24201d]',
  },
  drafting: {
    name: 'Context-Aware Drafter',
    role: 'Wordsmith',
    color: 'text-[#8b9bb4]',
    border: 'border-[#3f3a36]',
    bg: 'bg-[#24201d]',
  },
  critique: {
    name: 'Critique Agent',
    role: 'Inspector',
    color: 'text-[#b0a89f]',
    border: 'border-[#3f3a36]',
    bg: 'bg-[#24201d]',
  },
  polishing: {
    name: 'Polishing Agent',
    role: 'Prose Stylist',
    color: 'text-[#7fa678]',
    border: 'border-[#3f3a36]',
    bg: 'bg-[#24201d]',
  },
  chronicling: {
    name: 'Chronicler Agent',
    role: 'Memory Keeper',
    color: 'text-[#cf6659]',
    border: 'border-[#3f3a36]',
    bg: 'bg-[#24201d]',
  },
};

const PROVIDER_COLORS: Record<string, { badge: string; text: string; dot: string }> = {
  'Google Gemini': {
    badge: 'bg-[#383330] border-[#3f3a36] text-[#8b9bb4]',
    text: 'text-[#8b9bb4]',
    dot: 'bg-[#8b9bb4]',
  },
  'Google Gemma': {
    badge: 'bg-[#383330] border-[#3f3a36] text-[#b0a89f]',
    text: 'text-[#b0a89f]',
    dot: 'bg-[#b0a89f]',
  },
  OpenAI: {
    badge: 'bg-[#383330] border-[#3f3a36] text-[#7fa678]',
    text: 'text-[#7fa678]',
    dot: 'bg-[#7fa678]',
  },
  Anthropic: {
    badge: 'bg-[#383330] border-[#3f3a36] text-[#d9a05b]',
    text: 'text-[#d9a05b]',
    dot: 'bg-[#d9a05b]',
  },
  'Local Mock': {
    badge: 'bg-[#383330] border-[#3f3a36] text-[#857d75]',
    text: 'text-[#857d75]',
    dot: 'bg-[#857d75]',
  },
};

interface AggregatedStageMetrics {
  stage: string;
  agent: string;
  models: string[];
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  thoughtTokens: number;
  totalTokens: number;
  durationSeconds: number;
  interactionCount: number;
  cost: number;
}

interface AggregatedModelMetrics {
  model: string;
  provider: string;
  pricing: ModelPricing;
  callCount: number;
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  thoughtTokens: number;
  totalTokens: number;
  durationSeconds: number;
  cost: CostBreakdown;
  stages: string[];
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

  // Trace-level cost calculation
  const trCost = calculateCost(trTokens, currentTrace.model || 'unknown');

  // Canonical stages ordering
  const canonicalStages = ['extraction', 'drafting', 'critique', 'polishing', 'chronicling'];

  // Stages detailed token aggregation
  const stageMetricsMap: Record<string, AggregatedStageMetrics> = {};

  // Models detailed token and cost aggregation
  const modelMetricsMap: Record<string, AggregatedModelMetrics> = {};

  chapterDoc.traces.forEach((t) => {
    // 1. Stage aggregation
    const st = t.stage || 'unknown';
    if (!stageMetricsMap[st]) {
      stageMetricsMap[st] = {
        stage: st,
        agent: t.agent || st,
        models: [],
        inputTokens: 0,
        cachedTokens: 0,
        outputTokens: 0,
        thoughtTokens: 0,
        totalTokens: 0,
        durationSeconds: 0,
        interactionCount: 0,
        cost: 0,
      };
    }
    const sm = stageMetricsMap[st];
    const tu = t.token_usage || {
      input_tokens: 0,
      cached_tokens: 0,
      output_tokens: 0,
      thought_tokens: 0,
      total_tokens: 0,
    };
    sm.inputTokens += tu.input_tokens || 0;
    sm.cachedTokens += tu.cached_tokens || 0;
    sm.outputTokens += tu.output_tokens || 0;
    sm.thoughtTokens += tu.thought_tokens || 0;
    sm.totalTokens += tu.total_tokens || 0;
    sm.durationSeconds += t.duration_seconds || 0;
    sm.interactionCount += 1;
    if (t.model && !sm.models.includes(t.model)) {
      sm.models.push(t.model);
    }
    const costInfo = calculateCost(tu, t.model || 'unknown');
    sm.cost += costInfo.totalCost;

    // 2. Model aggregation
    const mName = t.model || 'unknown';
    if (!modelMetricsMap[mName]) {
      const pricing = getModelPricing(mName);
      modelMetricsMap[mName] = {
        model: mName,
        provider: pricing.provider,
        pricing,
        callCount: 0,
        inputTokens: 0,
        cachedTokens: 0,
        outputTokens: 0,
        thoughtTokens: 0,
        totalTokens: 0,
        durationSeconds: 0,
        cost: {
          freshInputCost: 0,
          cachedInputCost: 0,
          outputCost: 0,
          thoughtCost: 0,
          totalCost: 0,
          savingsFromCache: 0,
          formattedTotal: '$0.00',
          formattedSavings: '$0.00',
        },
        stages: [],
      };
    }
    const mm = modelMetricsMap[mName];
    mm.callCount += 1;
    mm.inputTokens += tu.input_tokens || 0;
    mm.cachedTokens += tu.cached_tokens || 0;
    mm.outputTokens += tu.output_tokens || 0;
    mm.thoughtTokens += tu.thought_tokens || 0;
    mm.totalTokens += tu.total_tokens || 0;
    mm.durationSeconds += t.duration_seconds || 0;
    if (t.stage && !mm.stages.includes(t.stage)) {
      mm.stages.push(t.stage);
    }
  });

  // Calculate total costs per model
  Object.values(modelMetricsMap).forEach((mm) => {
    mm.cost = calculateCost(
      {
        input_tokens: mm.inputTokens,
        cached_tokens: mm.cachedTokens,
        output_tokens: mm.outputTokens,
        thought_tokens: mm.thoughtTokens,
      },
      mm.model
    );
  });

  const modelEntries = Object.values(modelMetricsMap).sort(
    (a, b) => b.cost.totalCost - a.cost.totalCost || b.totalTokens - a.totalTokens
  );

  const chapterTotalCost = modelEntries.reduce((acc, m) => acc + m.cost.totalCost, 0);
  const chapterTotalSavings = modelEntries.reduce((acc, m) => acc + m.cost.savingsFromCache, 0);

  const stageEntries = Object.values(stageMetricsMap).sort((a, b) => {
    const idxA = canonicalStages.indexOf(a.stage);
    const idxB = canonicalStages.indexOf(b.stage);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return a.stage.localeCompare(b.stage);
  });

  return (
    <div className="space-y-4 overflow-y-auto max-h-full pr-1 font-sans">
      {/* Chapter Overview Cards */}
      <div>
        <div className="text-xs font-bold uppercase tracking-wider text-[#857d75] mb-2.5 flex items-center justify-between font-mono">
          <span className="flex items-center gap-1.5 text-[#f7f5f0]">
            <Layers className="w-3.5 h-3.5 text-[#b0a89f]" />
            <span>Chapter Performance & Allocation</span>
          </span>
          <span className="text-[11px] font-mono text-[#857d75] font-normal">
            Total Spend: <span className="text-[#d9a05b] font-semibold">{formatCost(chapterTotalCost)}</span>
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {/* Total Tokens */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36]">
            <div className="flex items-center gap-1.5 text-[#857d75] text-xs mb-1 font-mono">
              <Cpu className="w-3.5 h-3.5 text-[#b0a89f]" />
              <span>Total Tokens</span>
            </div>
            <div className="text-lg font-bold text-[#f7f5f0] font-mono">
              {chTokens.total_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 font-mono">
              {chapterDoc.total_interactions} interactions
            </div>
          </div>

          {/* Input Tokens */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36]">
            <div className="flex items-center gap-1.5 text-[#857d75] text-xs mb-1 font-mono">
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#8b9bb4]"></span>
              <span>Input Tokens</span>
            </div>
            <div className="text-lg font-bold text-[#8b9bb4] font-mono">
              {chTokens.input_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 font-mono">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.input_tokens / chTokens.total_tokens) * 100) : 0}% chapter
            </div>
          </div>

          {/* Cached Tokens (KV Cache) */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36] relative">
            <div className="flex items-center justify-between text-[#857d75] text-xs mb-1 font-mono">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-[#d9a05b]" />
                <span className="text-[#d9a05b]">Cached</span>
              </div>
              <span className="text-[9px] font-mono text-[#d9a05b] bg-[#24201d] border border-[#3f3a36] px-1 py-0.2 rounded-[2px]">
                KV
              </span>
            </div>
            <div className="text-lg font-bold text-[#d9a05b] font-mono">
              {chTokens.cached_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 font-mono">
              {cacheHitRate}% hit rate
            </div>
          </div>

          {/* Output Tokens */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36]">
            <div className="flex items-center gap-1.5 text-[#857d75] text-xs mb-1 font-mono">
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#7fa678]"></span>
              <span>Output Tokens</span>
            </div>
            <div className="text-lg font-bold text-[#7fa678] font-mono">
              {chTokens.output_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 font-mono">
              {chTokens.total_tokens > 0 ? Math.round((chTokens.output_tokens / chTokens.total_tokens) * 100) : 0}% chapter
            </div>
          </div>

          {/* Latency & Speed */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36]">
            <div className="flex items-center gap-1.5 text-[#857d75] text-xs mb-1 font-mono">
              <Zap className="w-3.5 h-3.5 text-[#d9a05b]" />
              <span>Throughput</span>
            </div>
            <div className="text-lg font-bold text-[#f7f5f0] font-mono">
              {chTps.toLocaleString()} <span className="text-[10px] text-[#857d75] font-normal">tok/s</span>
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 font-mono">
              {chapterDoc.total_duration_seconds.toFixed(1)}s total
            </div>
          </div>

          {/* Est. Chapter Cost */}
          <div className="p-3 rounded-[4px] bg-[#383330] border border-[#3f3a36] relative">
            <div className="flex items-center justify-between text-[#857d75] text-xs mb-1 font-mono">
              <div className="flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-[#d9a05b]" />
                <span className="text-[#d9a05b]">Cost</span>
              </div>
              {chapterTotalSavings > 0 && (
                <span className="text-[9px] font-mono text-[#7fa678] bg-[#24201d] border border-[#3f3a36] px-1 py-0.2 rounded-[2px]">
                  Saved
                </span>
              )}
            </div>
            <div className="text-lg font-bold text-[#d9a05b] font-mono">
              {formatCost(chapterTotalCost)}
            </div>
            <div className="text-[10px] text-[#857d75] mt-1 truncate font-mono">
              {chapterTotalSavings > 0 ? (
                <span className="text-[#7fa678]">-{formatCost(chapterTotalSavings)} KV</span>
              ) : (
                `${modelEntries.length} models`
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Model Consumption & Cost Breakdown Section */}
      <div className="p-3.5 rounded-[4px] bg-[#383330] border border-[#3f3a36] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#3f3a36]">
          <div className="flex items-center gap-2">
            <Coins className="w-3.5 h-3.5 text-[#d9a05b]" />
            <span className="text-xs font-semibold text-[#f7f5f0]">Model Consumption & Token Cost</span>
          </div>

          {/* Total Chapter Spend & KV Savings Badges */}
          <div className="flex items-center gap-2 text-xs font-mono">
            {chapterTotalSavings > 0 && (
              <span className="flex items-center gap-1 text-[11px] text-[#7fa678] bg-[#24201d] border border-[#3f3a36] px-2 py-0.5 rounded-[2px]">
                <Zap className="w-3 h-3 text-[#7fa678]" />
                <span>Saved {formatCost(chapterTotalSavings)}</span>
              </span>
            )}
            <span className="flex items-center gap-1 text-xs font-bold text-[#d9a05b] bg-[#24201d] border border-[#3f3a36] px-2 py-0.5 rounded-[2px]">
              <Coins className="w-3 h-3 text-[#d9a05b]" />
              <span>Chapter Total: {formatCost(chapterTotalCost)}</span>
            </span>
          </div>
        </div>

        {/* Model Cards Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
          {modelEntries.map((mm) => {
            const providerStyle = PROVIDER_COLORS[mm.provider] || {
              badge: 'bg-[#24201d] border-[#3f3a36] text-[#b0a89f]',
              text: 'text-[#b0a89f]',
              dot: 'bg-[#b0a89f]',
            };

            const freshInput = Math.max(0, mm.inputTokens - mm.cachedTokens);
            const cached = mm.cachedTokens;
            const thought = mm.thoughtTokens;
            const output = mm.outputTokens;
            const total = freshInput + cached + thought + output || mm.totalTokens || 1;

            const freshPct = (freshInput / total) * 100;
            const cachedPct = (cached / total) * 100;
            const thoughtPct = (thought / total) * 100;
            const outputPct = (output / total) * 100;

            const modelCostPct =
              chapterTotalCost > 0 ? Math.round((mm.cost.totalCost / chapterTotalCost) * 100) : 0;
            const modelCacheHitRate =
              mm.inputTokens > 0 ? Math.round((mm.cachedTokens / mm.inputTokens) * 100) : 0;

            return (
              <div
                key={mm.model}
                className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] space-y-2.5"
              >
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#f7f5f0]">
                      {mm.model}
                    </span>
                    <span
                      className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.2 rounded-[2px] border ${providerStyle.badge}`}
                    >
                      {mm.provider}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#857d75] font-mono">
                      {mm.callCount} {mm.callCount === 1 ? 'call' : 'calls'}
                    </span>
                  </div>

                  {/* Cost Highlight */}
                  <div className="text-right">
                    <div className="text-xs font-bold text-[#d9a05b] font-mono flex items-center gap-1 justify-end">
                      <Coins className="w-3 h-3 text-[#d9a05b]" />
                      <span>{mm.cost.formattedTotal}</span>
                    </div>
                    <div className="text-[10px] text-[#857d75] font-mono">
                      {modelCostPct}% chapter
                    </div>
                  </div>
                </div>

                {/* Model Tier Description */}
                {mm.pricing.description && (
                  <div className="text-[11px] text-[#857d75] italic flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-[1px] bg-[#857d75]"></span>
                    <span>{mm.pricing.description}</span>
                  </div>
                )}

                {/* Rates & Stages info */}
                <div className="flex flex-wrap items-center justify-between text-[11px] gap-2 text-[#857d75]">
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-[#857d75] text-[10px]">Stages:</span>
                    {mm.stages.map((st) => {
                      const stInfo = STAGE_AGENT_INFO[st];
                      return (
                        <span
                          key={st}
                          className={`text-[9px] font-mono px-1.5 py-0.2 rounded-[2px] border ${
                            stInfo
                              ? `${stInfo.bg} ${stInfo.border} ${stInfo.color}`
                              : 'bg-[#24201d] border-[#3f3a36] text-[#857d75]'
                          }`}
                        >
                          {stInfo ? stInfo.name : st}
                        </span>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-1.5 text-[10px] text-[#857d75] font-mono">
                    <span>${mm.pricing.inputPerMillion}/M In</span>
                    <span>·</span>
                    <span>${mm.pricing.cachedInputPerMillion}/M KV</span>
                    <span>·</span>
                    <span>${mm.pricing.outputPerMillion}/M Out</span>
                  </div>
                </div>

                {/* Token Distribution Stacked Bar */}
                <div className="w-full bg-[#24201d] rounded-[2px] h-2 overflow-hidden flex border border-[#3f3a36]">
                  {freshPct > 0 && (
                    <div
                      className="h-full bg-[#8b9bb4]"
                      style={{ width: `${freshPct}%` }}
                      title={`Input: ${freshInput.toLocaleString()} tok (${freshPct.toFixed(1)}%)`}
                    />
                  )}
                  {cachedPct > 0 && (
                    <div
                      className="h-full bg-[#d9a05b]"
                      style={{ width: `${cachedPct}%` }}
                      title={`KV Cache: ${cached.toLocaleString()} tok (${cachedPct.toFixed(1)}%, ${modelCacheHitRate}% hit)`}
                    />
                  )}
                  {thoughtPct > 0 && (
                    <div
                      className="h-full bg-[#b0a89f]"
                      style={{ width: `${thoughtPct}%` }}
                      title={`Reasoning: ${thought.toLocaleString()} tok (${thoughtPct.toFixed(1)}%)`}
                    />
                  )}
                  {outputPct > 0 && (
                    <div
                      className="h-full bg-[#7fa678]"
                      style={{ width: `${outputPct}%` }}
                      title={`Output: ${output.toLocaleString()} tok (${outputPct.toFixed(1)}%)`}
                    />
                  )}
                </div>

                {/* Cost & Token Breakdown Chips */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-0.5">
                  {/* Input Chip */}
                  <div className="p-1.5 rounded-[3px] bg-[#24201d] border border-[#3f3a36] text-xs font-mono">
                    <div className="flex items-center justify-between text-[#8b9bb4] text-[10px] mb-0.5">
                      <span>Input</span>
                      <span className="font-semibold">{formatMicroCost(mm.cost.freshInputCost)}</span>
                    </div>
                    <div className="font-bold text-[#f7f5f0] text-xs">
                      {freshInput.toLocaleString()} <span className="text-[10px] text-[#857d75] font-normal">tok</span>
                    </div>
                  </div>

                  {/* Cached Chip */}
                  <div className="p-1.5 rounded-[3px] bg-[#24201d] border border-[#3f3a36] text-xs font-mono">
                    <div className="flex items-center justify-between text-[#d9a05b] text-[10px] mb-0.5">
                      <span>KV Cache</span>
                      <span className="font-semibold">{formatMicroCost(mm.cost.cachedInputCost)}</span>
                    </div>
                    <div className="font-bold text-[#f7f5f0] text-xs">
                      {mm.cachedTokens.toLocaleString()} <span className="text-[10px] text-[#857d75] font-normal">tok</span>
                    </div>
                  </div>

                  {/* Thought Chip */}
                  <div className="p-1.5 rounded-[3px] bg-[#24201d] border border-[#3f3a36] text-xs font-mono">
                    <div className="flex items-center justify-between text-[#b0a89f] text-[10px] mb-0.5">
                      <span>Reasoning</span>
                      <span className="font-semibold">{formatMicroCost(mm.cost.thoughtCost)}</span>
                    </div>
                    <div className="font-bold text-[#f7f5f0] text-xs">
                      {mm.thoughtTokens.toLocaleString()} <span className="text-[10px] text-[#857d75] font-normal">tok</span>
                    </div>
                  </div>

                  {/* Output Chip */}
                  <div className="p-1.5 rounded-[3px] bg-[#24201d] border border-[#3f3a36] text-xs font-mono">
                    <div className="flex items-center justify-between text-[#7fa678] text-[10px] mb-0.5">
                      <span>Output</span>
                      <span className="font-semibold">{formatMicroCost(mm.cost.outputCost)}</span>
                    </div>
                    <div className="font-bold text-[#f7f5f0] text-xs">
                      {mm.outputTokens.toLocaleString()} <span className="text-[10px] text-[#857d75] font-normal">tok</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stage Breakdown Bar */}
      <div className="p-3.5 rounded-[4px] bg-[#383330] border border-[#3f3a36] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#3f3a36]">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-3.5 h-3.5 text-[#b0a89f]" />
            <span className="text-xs font-semibold text-[#f7f5f0]">Stage Token Distribution</span>
          </div>

          {/* Color Legend */}
          <div className="flex items-center gap-3 text-[10px] text-[#857d75] font-mono">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-[1px] bg-[#8b9bb4]"></span>
              <span>Input</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-[1px] bg-[#d9a05b]"></span>
              <span>Cached</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-[1px] bg-[#b0a89f]"></span>
              <span>Thought</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-[1px] bg-[#7fa678]"></span>
              <span>Output</span>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          {stageEntries.map((sm) => {
            const info = STAGE_AGENT_INFO[sm.stage] || {
              name: sm.agent,
              role: 'Agent',
              color: 'text-[#f7f5f0]',
              border: 'border-[#3f3a36]',
              bg: 'bg-[#24201d]',
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
              <div key={sm.stage} className="p-2.5 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] space-y-1.5">
                {/* Stage Header */}
                <div className="flex flex-wrap items-center justify-between text-xs gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.2 rounded-[2px] border ${info.bg} ${info.border} ${info.color}`}>
                      {info.name}
                    </span>
                    <span className="capitalize font-semibold text-[#f7f5f0]">
                      {sm.stage}
                    </span>
                    <span className="text-[11px] text-[#857d75]">
                      ({info.role})
                    </span>
                    {sm.interactionCount > 1 && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#857d75] font-mono">
                        {sm.interactionCount} calls
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-[11px] font-mono">
                    <span className="text-[#857d75]">{sm.durationSeconds.toFixed(1)}s</span>
                    <span className="font-semibold text-[#f7f5f0]">
                      {sm.totalTokens.toLocaleString()} tok
                      <span className="text-[#857d75] font-normal ml-1">({stageChapterPct}%)</span>
                    </span>
                    <span className="font-bold text-[#d9a05b] bg-[#24201d] border border-[#3f3a36] px-1.5 py-0.2 rounded-[2px] text-[10px]">
                      {formatCost(sm.cost)}
                    </span>
                  </div>
                </div>

                {/* Multi-Segment Stacked Bar */}
                <div className="w-full bg-[#24201d] rounded-[2px] h-2 overflow-hidden flex border border-[#3f3a36]">
                  {freshPct > 0 && (
                    <div
                      className="h-full bg-[#8b9bb4]"
                      style={{ width: `${freshPct}%` }}
                      title={`Input: ${freshInput.toLocaleString()} tok`}
                    />
                  )}
                  {cachedPct > 0 && (
                    <div
                      className="h-full bg-[#d9a05b]"
                      style={{ width: `${cachedPct}%` }}
                      title={`KV Cached: ${cached.toLocaleString()} tok (${stageCacheHitRate}% hit)`}
                    />
                  )}
                  {thoughtPct > 0 && (
                    <div
                      className="h-full bg-[#b0a89f]"
                      style={{ width: `${thoughtPct}%` }}
                      title={`Reasoning: ${thought.toLocaleString()} tok`}
                    />
                  )}
                  {outputPct > 0 && (
                    <div
                      className="h-full bg-[#7fa678]"
                      style={{ width: `${outputPct}%` }}
                      title={`Output: ${output.toLocaleString()} tok`}
                    />
                  )}
                </div>

                {/* Token Category Breakdown Chips */}
                <div className="flex flex-wrap items-center gap-2 pt-0.5 text-[10px] font-mono">
                  {/* Input */}
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#8b9bb4]">
                    <span>In:</span>
                    <span className="font-bold text-[#f7f5f0]">{sm.inputTokens.toLocaleString()}</span>
                  </div>

                  {/* Cached */}
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#d9a05b]">
                    <span>KV:</span>
                    <span className="font-bold text-[#f7f5f0]">{sm.cachedTokens.toLocaleString()}</span>
                    {sm.cachedTokens > 0 && (
                      <span className="text-[#857d75]">({stageCacheHitRate}%)</span>
                    )}
                  </div>

                  {/* Thought */}
                  {sm.thoughtTokens > 0 && (
                    <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#b0a89f]">
                      <span>Th:</span>
                      <span className="font-bold text-[#f7f5f0]">{sm.thoughtTokens.toLocaleString()}</span>
                    </div>
                  )}

                  {/* Output */}
                  <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] bg-[#24201d] border border-[#3f3a36] text-[#7fa678]">
                    <span>Out:</span>
                    <span className="font-bold text-[#f7f5f0]">{sm.outputTokens.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current Interaction Detail Gauge */}
      <div className="p-3.5 rounded-[4px] bg-[#383330] border border-[#3f3a36] space-y-2.5">
        <div className="text-xs font-semibold text-[#f7f5f0] flex items-center justify-between">
          <span className="flex items-center gap-2">
            <PieChart className="w-3.5 h-3.5 text-[#b0a89f]" />
            Selected Interaction: {currentTrace.agent} ({currentTrace.stage})
          </span>
          <div className="flex items-center gap-2 font-mono">
            {trTokens.cached_tokens > 0 && (
              <span className="text-[10px] text-[#d9a05b] bg-[#24201d] border border-[#3f3a36] px-1.5 py-0.2 rounded-[2px]">
                {trCacheHitRate}% KV Hit
              </span>
            )}
            <span className="text-[11px] text-[#857d75]">{trTokens.total_tokens.toLocaleString()} tok</span>
            <span className="text-xs font-bold text-[#d9a05b] bg-[#24201d] border border-[#3f3a36] px-2 py-0.5 rounded-[2px] flex items-center gap-1">
              <Coins className="w-3 h-3 text-[#d9a05b]" />
              {trCost.formattedTotal}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs font-mono">
          {/* Input */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[#857d75] text-[10px]">
              <span>Input</span>
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#8b9bb4]"></span>
            </div>
            <div className="text-sm font-bold text-[#8b9bb4] mt-0.5">
              {trTokens.input_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-0.5">
              {formatMicroCost(trCost.freshInputCost)}
            </div>
          </div>

          {/* Cached */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-[#d9a05b]">Cached</span>
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#d9a05b]"></span>
            </div>
            <div className="text-sm font-bold text-[#d9a05b] mt-0.5">
              {trTokens.cached_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-0.5">
              {formatMicroCost(trCost.cachedInputCost)}
            </div>
          </div>

          {/* Output */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[#857d75] text-[10px]">
              <span>Output</span>
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#7fa678]"></span>
            </div>
            <div className="text-sm font-bold text-[#7fa678] mt-0.5">
              {trTokens.output_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-0.5">
              {formatMicroCost(trCost.outputCost)}
            </div>
          </div>

          {/* Thought */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[#857d75] text-[10px]">
              <span>Thought</span>
              <span className="w-1.5 h-1.5 rounded-[1px] bg-[#b0a89f]"></span>
            </div>
            <div className="text-sm font-bold text-[#b0a89f] mt-0.5">
              {trTokens.thought_tokens.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#857d75] mt-0.5">
              {formatMicroCost(trCost.thoughtCost)}
            </div>
          </div>

          {/* Duration & Speed */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[#857d75] text-[10px]">
              <span>Duration</span>
              <Zap className="w-3 h-3 text-[#d9a05b]" />
            </div>
            <div className="text-sm font-bold text-[#d9a05b] mt-0.5">
              {currentTrace.duration_seconds.toFixed(2)}s
            </div>
            <div className="text-[10px] text-[#857d75] mt-0.5">
              {trTps} tok/s
            </div>
          </div>

          {/* Est. Cost */}
          <div className="p-2 rounded-[3px] bg-[#24201d] border border-[#3f3a36]">
            <div className="flex items-center justify-between text-[#857d75] text-[10px]">
              <span>Est. Cost</span>
              <Coins className="w-3 h-3 text-[#d9a05b]" />
            </div>
            <div className="text-sm font-bold text-[#d9a05b] mt-0.5">
              {trCost.formattedTotal}
            </div>
            <div className="text-[10px] text-[#857d75] truncate mt-0.5" title={currentTrace.model}>
              {currentTrace.model}
            </div>
          </div>
        </div>

        {/* Selected Interaction Stacked Bar */}
        {trTokens.total_tokens > 0 && (
          <div className="pt-0.5">
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
                <div className="w-full bg-[#24201d] rounded-[2px] h-1.5 overflow-hidden flex border border-[#3f3a36]">
                  {trFreshPct > 0 && (
                    <div className="h-full bg-[#8b9bb4]" style={{ width: `${trFreshPct}%` }} title={`Input: ${trFresh.toLocaleString()}`} />
                  )}
                  {trCachedPct > 0 && (
                    <div className="h-full bg-[#d9a05b]" style={{ width: `${trCachedPct}%` }} title={`Cached: ${trCached.toLocaleString()}`} />
                  )}
                  {trThoughtPct > 0 && (
                    <div className="h-full bg-[#b0a89f]" style={{ width: `${trThoughtPct}%` }} title={`Thought: ${trThought.toLocaleString()}`} />
                  )}
                  {trOutputPct > 0 && (
                    <div className="h-full bg-[#7fa678]" style={{ width: `${trOutputPct}%` }} title={`Output: ${trOutput.toLocaleString()}`} />
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
