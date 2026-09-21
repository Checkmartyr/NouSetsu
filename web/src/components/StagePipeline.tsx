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
}

const STAGES: StageMeta[] = [
  {
    key: 'extraction',
    label: '1. Extraction',
    agentName: 'EntityExtractor',
    icon: Search,
  },
  {
    key: 'drafting',
    label: '2. Drafting',
    agentName: 'ContextDrafter',
    icon: PenTool,
  },
  {
    key: 'critique',
    label: '3. Critique',
    agentName: 'CritiqueAgent',
    icon: CheckCircle,
  },
  {
    key: 'polishing',
    label: '4. Polishing',
    agentName: 'PolishingAgent',
    icon: Sparkles,
  },
  {
    key: 'chronicling',
    label: '5. Chronicler',
    agentName: 'ChroniclerAgent',
    icon: BookOpen,
  },
];

export const StagePipeline: React.FC<StagePipelineProps> = ({
  traces,
  selectedStageFilter,
  onSelectStageFilter,
}) => {
  return (
    <div className="bg-[#2b2622] border-b border-[#3f3a36] px-4 sm:px-6 py-2.5">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#dad2c1]">
              Pipeline Stage Progression
            </span>
            {selectedStageFilter && (
              <button
                onClick={() => onSelectStageFilter(null)}
                className="text-xs text-[#f7f5f0] hover:underline ml-2 cursor-pointer font-mono"
              >
                [Clear filter]
              </button>
            )}
          </div>
          <span className="text-[11px] text-[#aea69c]">
            Click stage to isolate interactions
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
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
                className={`flex flex-col p-2.5 rounded-[4px] border text-left transition-colors relative overflow-hidden group cursor-pointer ${
                  isSelected
                    ? 'bg-[#383330] border-[#f7f5f0] text-[#f7f5f0]'
                    : isPresent
                    ? 'bg-[#383330] border-[#3f3a36] hover:border-[#544d47] text-[#dad2c1]'
                    : 'bg-[#2b2622] border-[#3f3a36] opacity-40 hover:opacity-70 text-[#aea69c]'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <div className="flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5 text-[#c9c0ad]" />
                    <span className="text-xs font-medium text-[#f7f5f0]">{s.label}</span>
                  </div>
                  {count > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#dad2c1] border border-[#3f3a36]">
                      {count}
                    </span>
                  )}
                </div>

                <div className="text-[10px] font-mono text-[#aea69c] truncate mb-1">
                  {s.agentName}
                </div>

                <div className="flex items-center justify-between mt-auto pt-1 border-t border-[#3f3a36] text-[10px] font-mono text-[#aea69c]">
                  <span>{isPresent ? `${stageTokens.toLocaleString()} tok` : 'Skipped'}</span>
                  <div className="flex items-center gap-1">
                    {hasError && (
                      <span title="Has errors">
                        <AlertTriangle className="w-3 h-3 text-rose-400" />
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
