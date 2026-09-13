import React from 'react';
import { PipelineStage, AgentPromptTrace } from '../types/trace';
import { Search, PenTool, CheckCircle, Sparkles, BookOpen, AlertTriangle, ShieldAlert } from 'lucide-react';

interface StagePipelineProps {
  traces: AgentPromptTrace[];
  selectedStageFilter: string | null;
  onSelectStageFilter: (stage: string | null) => void;
}

interface StageMeta {
  key: PipelineStage;
  label: string;
  agentName: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
}

const STAGES: StageMeta[] = [
  {
    key: 'extraction',
    label: 'Extraction',
    agentName: 'EntityExtractorAgent',
    icon: Search,
    color: 'text-amber-400',
    bgColor: 'bg-amber-400/10',
    borderColor: 'border-amber-500/30',
  },
  {
    key: 'drafting',
    label: 'Drafting',
    agentName: 'ContextAwareDrafter',
    icon: PenTool,
    color: 'text-blue-400',
    bgColor: 'bg-blue-400/10',
    borderColor: 'border-blue-500/30',
  },
  {
    key: 'critique',
    label: 'Critique',
    agentName: 'CritiqueAgent',
    icon: CheckCircle,
    color: 'text-purple-400',
    bgColor: 'bg-purple-400/10',
    borderColor: 'border-purple-500/30',
  },
  {
    key: 'polishing',
    label: 'Polishing',
    agentName: 'PolishingAgent',
    icon: Sparkles,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-400/10',
    borderColor: 'border-emerald-500/30',
  },
  {
    key: 'chronicling',
    label: 'Chronicling',
    agentName: 'ChroniclerAgent',
    icon: BookOpen,
    color: 'text-rose-400',
    bgColor: 'bg-rose-400/10',
    borderColor: 'border-rose-500/30',
  },
];

export const StagePipeline: React.FC<StagePipelineProps> = ({
  traces,
  selectedStageFilter,
  onSelectStageFilter,
}) => {
  return (
    <div className="bg-slate-900/50 border-b border-slate-800/80 px-4 sm:px-6 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Pipeline Stage Progression
            </span>
            {selectedStageFilter && (
              <button
                onClick={() => onSelectStageFilter(null)}
                className="text-xs text-indigo-400 hover:text-indigo-300 underline underline-offset-2 ml-2"
              >
                Clear stage filter
              </button>
            )}
          </div>
          <span className="text-xs text-slate-500">
            Click a stage to isolate interactions
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
          {STAGES.map((s) => {
            const stageTraces = traces.filter((t) => t.stage === s.key);
            const count = stageTraces.length;
            const isPresent = count > 0;
            const isSelected = selectedStageFilter === s.key;
            const hasError = stageTraces.some((t) => t.status === 'error');
            const hasSafety = stageTraces.some((t) => t.status === 'safety_blocked');
            const stageTokens = stageTraces.reduce(
              (sum, t) => sum + (t.token_usage?.total_tokens || 0),
              0
            );

            const Icon = s.icon;

            return (
              <button
                key={s.key}
                type="button"
                onClick={() => onSelectStageFilter(isSelected ? null : s.key)}
                className={`flex flex-col p-2.5 rounded-xl border text-left transition-all relative overflow-hidden group ${
                  isSelected
                    ? `${s.bgColor} ${s.borderColor} ring-2 ring-indigo-500 shadow-md`
                    : isPresent
                    ? 'bg-slate-900/90 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
                    : 'bg-slate-950/40 border-slate-850 opacity-40 hover:opacity-70'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <div className="flex items-center gap-1.5">
                    <div className={`p-1 rounded-md ${s.bgColor}`}>
                      <Icon className={`w-3.5 h-3.5 ${s.color}`} />
                    </div>
                    <span className="text-xs font-semibold text-slate-200">{s.label}</span>
                  </div>
                  {count > 0 && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                      {count}
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400 truncate mb-1">
                  {s.agentName}
                </div>

                <div className="flex items-center justify-between mt-auto pt-1 border-t border-slate-800/60 text-[10px] text-slate-400">
                  <span>{isPresent ? `${stageTokens.toLocaleString()} tok` : 'Skipped'}</span>
                  <div className="flex items-center gap-1">
                    {hasError && (
                      <span title="Has errors">
                        <AlertTriangle className="w-3 h-3 text-red-400" />
                      </span>
                    )}
                    {hasSafety && (
                      <span title="Safety blocked">
                        <ShieldAlert className="w-3 h-3 text-amber-400" />
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
