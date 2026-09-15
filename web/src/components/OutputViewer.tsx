import React, { useState } from 'react';
import { AgentPromptTrace } from '../types/trace';
import { extractJsonFromText } from '../utils/jsonParser';
import { estimateTokens } from '../utils/tokenEstimator';
import { Copy, Check, FileText, Code2, AlertTriangle, ShieldAlert, Sparkles, MessageSquare } from 'lucide-react';

interface OutputViewerProps {
  trace: AgentPromptTrace;
}

export const OutputViewer: React.FC<OutputViewerProps> = ({ trace }) => {
  const [viewMode, setViewMode] = useState<'formatted' | 'raw'>('formatted');
  const [copied, setCopied] = useState(false);

  const rawOutput = trace.raw_output || '';

  // Extract JSON whether plain, markdown-fenced (```json ... ```), or embedded
  const extracted = extractJsonFromText(rawOutput);
  const parsedJson = extracted?.parsed ?? null;
  const isJsonLike = parsedJson !== null;

  const handleCopy = () => {
    navigator.clipboard.writeText(rawOutput);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyJsonOnly = () => {
    if (parsedJson) {
      navigator.clipboard.writeText(JSON.stringify(parsedJson, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Top action bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setViewMode('formatted')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                viewMode === 'formatted' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>{isJsonLike ? 'Formatted JSON' : 'Prose View'}</span>
            </button>
            <button
              onClick={() => setViewMode('raw')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                viewMode === 'raw' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Raw Text</span>
            </button>
          </div>

          {isJsonLike && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
              <Sparkles className="w-3 h-3" />
              <span>JSON Detected</span>
            </span>
          )}

          <span className="text-xs text-slate-400">
            <span className="font-semibold text-slate-200">
              {(trace.token_usage?.output_tokens && trace.token_usage.output_tokens > 0
                ? trace.token_usage.output_tokens
                : estimateTokens(rawOutput)
              ).toLocaleString()} tokens
            </span>
            <span className="text-[10px] text-slate-500 ml-1">
              {trace.token_usage?.output_tokens && trace.token_usage.output_tokens > 0 ? '(measured)' : '(est.)'}
            </span>
            <span className="mx-1.5 text-slate-600">•</span>
            <span>{rawOutput.length.toLocaleString()} chars</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isJsonLike && (
            <button
              onClick={handleCopyJsonOnly}
              className="flex items-center gap-1 text-xs text-slate-300 hover:text-white px-2 py-1 bg-slate-850 hover:bg-slate-750 border border-slate-750 rounded-lg transition-colors"
              title="Copy cleanly formatted JSON payload"
            >
              <Copy className="w-3 h-3 text-indigo-400" />
              <span className="hidden sm:inline">Copy JSON</span>
            </button>
          )}

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-slate-300 hover:text-white px-2.5 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied!' : 'Copy Raw'}</span>
          </button>
        </div>
      </div>

      {/* Safety Alert or Error Notice */}
      {trace.status === 'safety_blocked' && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 shrink-0 text-amber-400" />
          <div>
            <div className="font-semibold">Generation Blocked by Safety Filters</div>
            <p className="text-amber-400/80 mt-0.5">{trace.error_message || 'Content triggered automated provider safety filter.'}</p>
          </div>
        </div>
      )}

      {trace.status === 'error' && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0 text-red-400" />
          <div>
            <div className="font-semibold">Execution Error Occurred</div>
            <p className="text-red-400/80 mt-0.5">{trace.error_message || 'Unknown generation failure.'}</p>
          </div>
        </div>
      )}

      {/* Output Content Display */}
      <div className="flex-1 overflow-y-auto bg-slate-900/60 border border-slate-800 rounded-xl p-6">
        {viewMode === 'raw' ? (
          <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed selection:bg-indigo-900">
            {rawOutput || '<Empty Output>'}
          </pre>
        ) : isJsonLike ? (
          <div className="space-y-4">
            {/* Optional Preamble Text (e.g. LLM introductory comment) */}
            {extracted?.preamble && (
              <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-300 flex items-start gap-2 italic">
                <MessageSquare className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                <div>{extracted.preamble}</div>
              </div>
            )}

            {/* 1. Extraction Agent Output Cards */}
            {parsedJson.new_characters && (
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-2">
                  Extracted Characters ({parsedJson.new_characters.length})
                </h4>
                <div className="grid sm:grid-cols-2 gap-3">
                  {parsedJson.new_characters.map((ch: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">{ch.name}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 capitalize">
                          {ch.role || 'character'}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">{ch.original_name}</div>
                      {ch.voice && <div className="text-slate-300 text-[11px] italic">"{ch.voice}"</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {parsedJson.new_terms && (
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-blue-400 mb-2">
                  Extracted Terminology ({parsedJson.new_terms.length})
                </h4>
                <div className="grid sm:grid-cols-2 gap-3">
                  {parsedJson.new_terms.map((tm: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">{tm.source} ➔ {tm.target}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 capitalize">
                          {tm.category || 'term'}
                        </span>
                      </div>
                      {tm.notes && <div className="text-slate-400 text-[11px]">{tm.notes}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 2. Critique Agent Output Cards */}
            {(parsedJson.critique_notes || parsedJson.fidelity_score !== undefined || parsedJson.style_score !== undefined) && (
              <div>
                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400">
                    Audit & Critique Evaluation
                  </h4>
                  {parsedJson.fidelity_score !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30">
                      Fidelity: {parsedJson.fidelity_score}/10
                    </span>
                  )}
                  {parsedJson.flow_score !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold border border-blue-500/30">
                      Flow: {parsedJson.flow_score}/10
                    </span>
                  )}
                  {parsedJson.style_score !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold border border-blue-500/30">
                      Style: {parsedJson.style_score}/10
                    </span>
                  )}
                  {parsedJson.glossary_compliance_pct !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">
                      Glossary: {parsedJson.glossary_compliance_pct}%
                    </span>
                  )}
                </div>

                {/* Warnings list if present */}
                {parsedJson.warnings && Array.isArray(parsedJson.warnings) && parsedJson.warnings.length > 0 && (
                  <div className="mb-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-1">
                    <div className="font-semibold text-[11px] uppercase tracking-wider text-amber-400">Warnings:</div>
                    <ul className="list-disc list-inside space-y-0.5 text-amber-200">
                      {parsedJson.warnings.map((w: string, i: number) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Detailed critique notes */}
                {Array.isArray(parsedJson.critique_notes) ? (
                  <div className="space-y-3">
                    {parsedJson.critique_notes.map((note: any, idx: number) => (
                      <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-slate-300">Target: "{note.target || 'General'}"</span>
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                            {note.severity || 'note'}
                          </span>
                        </div>
                        <div className="text-slate-400">{note.issue || note}</div>
                        {note.suggestion && (
                          <div className="p-2 rounded bg-emerald-950/40 border border-emerald-900/60 text-emerald-300 text-[11px]">
                            <span className="font-semibold">Suggestion: </span>{note.suggestion}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : typeof parsedJson.critique_notes === 'string' ? (
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 leading-relaxed">
                    {parsedJson.critique_notes}
                  </div>
                ) : null}
              </div>
            )}

            {/* 3. Chronicler Agent Output Cards */}
            {parsedJson.chapter_summary && (
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400">
                  Chapter Chronicle & Memory
                </h4>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-2">
                  <div className="font-semibold text-slate-200">Synopsis:</div>
                  <p className="text-slate-300 leading-relaxed">{parsedJson.chapter_summary}</p>
                </div>

                {parsedJson.character_status_updates && (
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-2">
                    <div className="font-semibold text-slate-200">Character Status Updates:</div>
                    <div className="space-y-1">
                      {Object.entries(parsedJson.character_status_updates).map(([char, status], i) => (
                        <div key={i} className="text-slate-300">
                          <span className="font-medium text-indigo-300">{char}: </span>
                          <span className="text-slate-400">{String(status)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {parsedJson.new_foreshadowing_flags && (
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                    <div className="font-semibold text-slate-200">Foreshadowing & Continuity Flags:</div>
                    <ul className="list-disc list-inside text-slate-400 space-y-0.5">
                      {parsedJson.new_foreshadowing_flags.map((flag: string, i: number) => (
                        <li key={i}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* 4. Generic / Raw JSON Pretty Print (if not matching custom domain cards) */}
            {!parsedJson.new_characters && !parsedJson.critique_notes && !parsedJson.chapter_summary && (
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-4">
                <pre className="font-mono text-xs text-indigo-300 whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(parsedJson, null, 2)}
                </pre>
              </div>
            )}

            {/* Optional Postscript Text */}
            {extracted?.postscript && (
              <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-400 flex items-start gap-2 italic">
                <MessageSquare className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                <div>{extracted.postscript}</div>
              </div>
            )}
          </div>
        ) : (
          /* Rich Literary Prose View with Paragraphs */
          <div className="max-w-3xl mx-auto font-serif-prose text-slate-200 text-base leading-loose space-y-4">
            {rawOutput.split('\n\n').map((paragraph, i) => (
              <p key={i} className="tracking-wide">
                {paragraph}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
