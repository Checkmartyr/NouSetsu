import React, { useEffect, useState } from 'react';
import { AlertTriangle, BarChart3, Clock3, Cpu, Database, Layers3, RefreshCw } from 'lucide-react';
import { fetchProjectTokenAnalytics } from '../services/apiClient';
import { ProjectTokenAnalyticsResponse, ProjectTokenSummary, TokenMetricTotals } from '../types/dashboard';

interface ProjectTokenAnalyticsProps {
  projectPath: string | null;
  projectTitle: string | null;
  refreshKey?: string;
}

const formatNumber = (value: number) => value.toLocaleString();

function formatDuration(seconds: number): string {
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  if (seconds >= 60) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${seconds.toFixed(seconds % 1 ? 1 : 0)}s`;
}

const MetricCard: React.FC<{ label: string; value: string; detail?: string }> = ({ label, value, detail }) => (
  <div className="rounded-[4px] border border-[#3f3a36] bg-[#383330] p-3">
    <div className="text-[11px] font-mono uppercase tracking-wide text-[#aea69c]">{label}</div>
    <div className="mt-1 text-xl font-semibold font-mono text-[#f7f5f0]">{value}</div>
    {detail && <div className="mt-1 text-[10px] text-[#aea69c]">{detail}</div>}
  </div>
);

const Section: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode }> = ({ title, icon, children }) => (
  <section className="rounded-[4px] border border-[#3f3a36] bg-[#2b2622]">
    <h2 className="flex items-center gap-2 border-b border-[#3f3a36] px-4 py-3 text-sm font-medium text-[#f7f5f0]">
      {icon}
      {title}
    </h2>
    {children}
  </section>
);

const tokenColumns = (item: TokenMetricTotals) => ({
  total: item.total_tokens,
  input: item.input_tokens,
  output: item.output_tokens,
  thought: item.thought_tokens,
  cached: item.cached_tokens,
  duration: item.duration_seconds,
});

function MetricTable({ summary, kind }: { summary: ProjectTokenSummary; kind: 'stage' | 'model' | 'folder' | 'chapter' }) {
  const rows = kind === 'stage'
    ? summary.stage_metrics.map((item) => ({
      key: item.stage, label: item.stage, scope: '', count: item.calls, ...tokenColumns(item),
    }))
    : kind === 'model'
      ? summary.model_metrics.map((item) => ({
        key: item.model, label: item.model, scope: '', count: item.calls, ...tokenColumns(item),
      }))
      : kind === 'folder'
        ? summary.folder_metrics.map((item) => ({
          key: item.folder, label: item.folder === 'default' ? 'Root chapters' : item.folder,
          scope: '', count: item.analyzed_chapters || item.chapter_count, ...tokenColumns(item),
        }))
        : summary.chapter_rankings.map((item) => ({
          key: item.chapter_id, label: `Ch. ${item.chapter_num} · ${item.source_file}`,
          scope: item.folder === 'default' ? 'Root chapters' : item.folder,
          count: 1, total: item.total_tokens, input: item.prompt_tokens,
          output: item.completion_tokens, thought: item.thought_tokens,
          cached: item.cached_tokens, duration: item.duration_seconds,
        }));

  if (!rows.length) {
    return <p className="px-4 py-5 text-xs text-[#aea69c]">No recorded token usage in this scope.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-[10px] uppercase tracking-wide text-[#aea69c]">
          <tr className="border-b border-[#3f3a36]">
            <th className="px-4 py-2 font-medium">{kind === 'chapter' ? 'Chapter' : kind}</th>
            <th className="px-3 py-2 text-right font-medium">{kind === 'chapter' ? 'Folder' : 'Calls / chapters'}</th>
            <th className="px-3 py-2 text-right font-medium">Tokens</th>
            <th className="px-3 py-2 text-right font-medium">Input</th>
            <th className="px-3 py-2 text-right font-medium">Output</th>
            <th className="px-3 py-2 text-right font-medium">Thought</th>
            <th className="px-3 py-2 text-right font-medium">Cached</th>
            <th className="px-4 py-2 text-right font-medium">Duration</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.key} className={index < rows.length - 1 ? 'border-b border-[#3f3a36]/70' : ''}>
              <td className="px-4 py-2.5 font-medium text-[#f7f5f0] capitalize">{row.label}</td>
              <td className="px-3 py-2.5 text-right text-[#c9c0ad]">{kind === 'chapter' ? row.scope : formatNumber(row.count)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-[#f7f5f0]">{formatNumber(row.total)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-[#8b9bb4]">{formatNumber(row.input)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-[#7fa678]">{formatNumber(row.output)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-[#c9c0ad]">{formatNumber(row.thought)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-[#c9c0ad]">{formatNumber(row.cached)}</td>
              <td className="px-4 py-2.5 text-right font-mono text-[#c9c0ad]">{formatDuration(row.duration)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const ProjectTokenAnalytics: React.FC<ProjectTokenAnalyticsProps> = ({ projectPath, projectTitle, refreshKey }) => {
  const [folder, setFolder] = useState('ALL');
  const [analytics, setAnalytics] = useState<ProjectTokenAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    if (!projectPath) {
      setAnalytics(null);
      setLoading(false);
      setFailed(false);
      return () => { current = false; };
    }

    setLoading(true);
    setFailed(false);
    fetchProjectTokenAnalytics(projectPath, folder === 'ALL' ? undefined : folder).then((result) => {
      if (!current) return;
      setAnalytics(result);
      setFailed(result === null);
      setLoading(false);
    });
    return () => { current = false; };
  }, [projectPath, folder, refreshKey]);

  const summary = analytics?.recorded;
  const cards = summary ? [
    { label: 'Recorded tokens', value: formatNumber(summary.total_tokens), detail: `${summary.analyzed_chapters} chapters with recorded usage` },
    { label: 'Prompt tokens', value: formatNumber(summary.prompt_tokens) },
    { label: 'Completion tokens', value: formatNumber(summary.completion_tokens) },
    { label: 'Thought tokens', value: formatNumber(summary.thought_tokens) },
    { label: 'Cached tokens', value: formatNumber(summary.cached_tokens) },
    { label: 'Recorded duration', value: formatDuration(summary.total_duration_seconds) },
  ] : [];

  return (
    <main className="min-h-0 flex-1 overflow-y-auto bg-[#24201d] p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-lg font-medium text-[#f7f5f0]">Project Token Analysis</h1>
            <p className="mt-1 text-xs text-[#aea69c]">{projectTitle || 'Active project'} · recorded usage across translation attempts</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-[#c9c0ad]">
            Volume folder
            <select
              aria-label="Filter by volume folder"
              value={folder}
              onChange={(event) => setFolder(event.target.value)}
              className="min-w-40 rounded-[3px] border border-[#3f3a36] bg-[#383330] px-2.5 py-1.5 text-[#f7f5f0] focus:outline-none focus:border-[#dad2c1]"
            >
              <option value="ALL">All volume folders</option>
              {(analytics?.available_folders || []).map((item) => (
                <option key={item} value={item}>{item === 'default' ? 'Root chapters' : item}</option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 rounded-[4px] border border-[#3f3a36] bg-[#2b2622] p-5 text-sm text-[#c9c0ad]">
            <RefreshCw className="h-4 w-4 animate-spin" /> Loading project token history…
          </div>
        ) : failed ? (
          <div role="alert" className="rounded-[4px] border border-rose-900/60 bg-rose-950/30 p-4 text-sm text-rose-200">
            Could not load token analytics for this project. Try switching projects or refreshing.
          </div>
        ) : !analytics || !summary ? (
          <div className="rounded-[4px] border border-[#3f3a36] bg-[#2b2622] p-5 text-sm text-[#aea69c]">
            Select an active project to view token history.
          </div>
        ) : (
          <>
            {!analytics.coverage.history_complete && (
              <div className="flex items-start gap-2 rounded-[4px] border border-amber-800/50 bg-amber-950/25 p-3 text-xs text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>
                  Trace history is incomplete. Recorded totals include trace records and metadata snapshots with per-step usage; estimated metadata is excluded.
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
              {cards.map((card) => <MetricCard key={card.label} {...card} />)}
            </div>

            <div className="flex items-start gap-2 rounded-[4px] border border-[#3f3a36] bg-[#2b2622] px-3 py-2.5 text-xs text-[#c9c0ad]">
              <Database className="mt-0.5 h-4 w-4 shrink-0 text-[#aea69c]" />
              <span>
                Metadata-only snapshot: <strong className="text-[#f7f5f0]">{formatNumber(analytics.metadata_snapshot.total_tokens)} tokens</strong> across {analytics.metadata_snapshot.total_chapters} {analytics.metadata_snapshot.total_chapters === 1 ? 'chapter' : 'chapters'} with recorded step usage. This is included once in project totals; chapters without recorded steps are excluded. This view is not a billing ledger.
              </span>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <Section title="By processing stage" icon={<Layers3 className="h-4 w-4 text-[#8b9bb4]" />}>
                <MetricTable summary={summary} kind="stage" />
              </Section>
              <Section title="By model" icon={<Cpu className="h-4 w-4 text-[#7fa678]" />}>
                <MetricTable summary={summary} kind="model" />
              </Section>
              <Section title="By volume folder" icon={<BarChart3 className="h-4 w-4 text-[#d9a05b]" />}>
                <MetricTable summary={summary} kind="folder" />
              </Section>
              <Section title="Chapter usage" icon={<Clock3 className="h-4 w-4 text-[#cf6659]" />}>
                <MetricTable summary={summary} kind="chapter" />
              </Section>
              {analytics.metadata_snapshot.total_chapters > 0 && (
                <Section title="Metadata snapshots with recorded usage" icon={<Database className="h-4 w-4 text-[#aea69c]" />}>
                  <MetricTable summary={analytics.metadata_snapshot} kind="chapter" />
                </Section>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
};
