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
    <div className="flex flex-col h-full space-y-3 font-sans">
      {/* Top action bar */}
      <div className="flex items-center justify-between pb-2 border-b border-[#3f3a36]">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 bg-[#24201d] p-0.5 rounded-[3px] border border-[#3f3a36]">
            <button
              onClick={() => setViewMode('formatted')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] text-xs font-medium transition-colors ${
                viewMode === 'formatted'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold shadow-xs'
                  : 'text-[#b0a89f] hover:text-[#f7f5f0]'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>{isJsonLike ? 'Formatted JSON' : 'Prose View'}</span>
            </button>
            <button
              onClick={() => setViewMode('raw')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] text-xs font-medium transition-colors ${
                viewMode === 'raw'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold shadow-xs'
                  : 'text-[#b0a89f] hover:text-[#f7f5f0]'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Raw Text</span>
            </button>
          </div>

          {isJsonLike && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#e2ded6] border border-[#3f3a36] font-mono">
              <Sparkles className="w-3 h-3 text-[#d9a05b]" />
              <span>JSON Detected</span>
            </span>
          )}

          <span className="text-xs text-[#857d75] font-mono">
            <span className="font-semibold text-[#b0a89f]">
              {(trace.token_usage?.output_tokens && trace.token_usage.output_tokens > 0
                ? trace.token_usage.output_tokens
                : estimateTokens(rawOutput)
              ).toLocaleString()} tok
            </span>
            <span className="text-[10px] text-[#857d75] ml-1">
              {trace.token_usage?.output_tokens && trace.token_usage.output_tokens > 0 ? '(measured)' : '(est.)'}
            </span>
            <span className="mx-1.5 text-[#3f3a36]">•</span>
            <span>{rawOutput.length.toLocaleString()} chars</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isJsonLike && (
            <button
              onClick={handleCopyJsonOnly}
              className="flex items-center gap-1 text-xs text-[#b0a89f] hover:text-[#f7f5f0] px-2.5 py-1 bg-[#383330] hover:bg-[#3f3a36] border border-[#3f3a36] rounded-[3px] transition-colors font-mono"
              title="Copy cleanly formatted JSON payload"
            >
              <Copy className="w-3 h-3 text-[#b0a89f]" />
              <span className="hidden sm:inline">Copy JSON</span>
            </button>
          )}

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-[#f7f5f0] px-2.5 py-1 bg-[#383330] hover:bg-[#3f3a36] border border-[#3f3a36] rounded-[3px] transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#7fa678]" /> : <Copy className="w-3.5 h-3.5 text-[#b0a89f]" />}
            <span>{copied ? 'Copied' : 'Copy Raw'}</span>
          </button>
        </div>
      </div>

      {/* Safety Alert or Error Notice */}
      {trace.status === 'safety_blocked' && (
        <div className="p-3 rounded-[4px] bg-[#382b22] border border-[#a86532]/50 text-[#e6a573] text-xs flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 shrink-0 text-[#e6a573]" />
          <div>
            <div className="font-semibold">Generation Blocked by Safety Filters</div>
            <p className="text-[#d48e58] mt-0.5">{trace.error_message || 'Content triggered automated provider safety filter.'}</p>
          </div>
        </div>
      )}

      {trace.status === 'error' && (
        <div className="p-3 rounded-[4px] bg-[#382522] border border-[#a83d32]/50 text-[#e67b73] text-xs flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0 text-[#e67b73]" />
          <div>
            <div className="font-semibold">Execution Error Occurred</div>
            <p className="text-[#cf6659] mt-0.5">{trace.error_message || 'Unknown generation failure.'}</p>
          </div>
        </div>
      )}

      {/* Output Content Display */}
      <div className="flex-1 overflow-y-auto bg-[#24201d] border border-[#3f3a36] rounded-[4px] p-5">
        {viewMode === 'raw' ? (
          <pre className="font-mono text-xs text-[#b0a89f] whitespace-pre-wrap leading-relaxed selection:bg-[#383330] selection:text-[#f7f5f0]">
            {rawOutput || '<Empty Output>'}
          </pre>
        ) : isJsonLike ? (
          <div className="space-y-4">
            {/* Optional Preamble Text (e.g. LLM introductory comment) */}
            {extracted?.preamble && (
              <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs text-[#b0a89f] flex items-start gap-2 italic">
                <MessageSquare className="w-4 h-4 text-[#857d75] shrink-0 mt-0.5" />
                <div>{extracted.preamble}</div>
              </div>
            )}

            {/* 1. Extraction Agent Output Cards */}
            {parsedJson.new_characters && (
              <div>
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#d9a05b] mb-2 font-mono">
                  Extracted Characters ({parsedJson.new_characters.length})
                </h4>
                <div className="grid sm:grid-cols-2 gap-2.5">
                  {parsedJson.new_characters.map((ch: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-[#f7f5f0]">{ch.name}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#383330] text-[#d9a05b] border border-[#3f3a36] capitalize">
                          {ch.role || 'character'}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#857d75] font-mono">{ch.original_name}</div>
                      {ch.voice && <div className="text-[#b0a89f] text-[11px] italic">"{ch.voice}"</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {parsedJson.new_terms && (
              <div>
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#8b9bb4] mb-2 font-mono">
                  Extracted Terminology ({parsedJson.new_terms.length})
                </h4>
                <div className="grid sm:grid-cols-2 gap-2.5">
                  {parsedJson.new_terms.map((tm: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-[#f7f5f0]">{tm.source} ➔ {tm.target}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#383330] text-[#8b9bb4] border border-[#3f3a36] capitalize">
                          {tm.category || 'term'}
                        </span>
                      </div>
                      {tm.notes && <div className="text-[#857d75] text-[11px]">{tm.notes}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 2. Critique Agent Output Cards */}
            {(parsedJson.critique_notes || parsedJson.fidelity_score !== undefined || parsedJson.style_score !== undefined) && (
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#b0a89f] font-mono">
                    Audit & Critique Evaluation
                  </h4>
                  {parsedJson.fidelity_score !== undefined && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#f7f5f0] font-semibold border border-[#3f3a36]">
                      Fidelity: {parsedJson.fidelity_score}/10
                    </span>
                  )}
                  {parsedJson.flow_score !== undefined && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#8b9bb4] font-semibold border border-[#3f3a36]">
                      Flow: {parsedJson.flow_score}/10
                    </span>
                  )}
                  {parsedJson.style_score !== undefined && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#d9a05b] font-semibold border border-[#3f3a36]">
                      Style: {parsedJson.style_score}/10
                    </span>
                  )}
                  {parsedJson.glossary_compliance_pct !== undefined && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#7fa678] font-semibold border border-[#3f3a36]">
                      Glossary: {parsedJson.glossary_compliance_pct}%
                    </span>
                  )}
                </div>

                {/* Warnings list if present */}
                {parsedJson.warnings && Array.isArray(parsedJson.warnings) && parsedJson.warnings.length > 0 && (
                  <div className="mb-3 p-3 rounded-[3px] bg-[#382b22] border border-[#a86532]/40 text-xs text-[#e6a573] space-y-1">
                    <div className="font-semibold text-[11px] uppercase tracking-wider text-[#d9a05b] font-mono">Warnings:</div>
                    <ul className="list-disc list-inside space-y-0.5 text-[#e2ded6]">
                      {parsedJson.warnings.map((w: string, i: number) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Detailed critique notes */}
                {Array.isArray(parsedJson.critique_notes) ? (
                  <div className="space-y-2.5">
                    {parsedJson.critique_notes.map((note: any, idx: number) => (
                      <div key={idx} className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-[#f7f5f0]">Target: "{note.target || 'General'}"</span>
                          <span className="text-[10px] font-mono uppercase font-bold px-1.5 py-0.5 rounded-[2px] bg-[#383330] text-[#b0a89f] border border-[#3f3a36]">
                            {note.severity || 'note'}
                          </span>
                        </div>
                        <div className="text-[#857d75]">{note.issue || note}</div>
                        {note.suggestion && (
                          <div className="p-2 rounded-[2px] bg-[#272f26] border border-[#7fa678]/40 text-[#a5c49f] text-[11px]">
                            <span className="font-semibold">Suggestion: </span>{note.suggestion}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : typeof parsedJson.critique_notes === 'string' ? (
                  <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs text-[#b0a89f] leading-relaxed">
                    {parsedJson.critique_notes}
                  </div>
                ) : null}
              </div>
            )}

            {/* 3. Chronicler Agent Output Cards */}
            {parsedJson.chapter_summary && (
              <div className="space-y-2.5">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-[#cf6659] font-mono">
                  Chapter Chronicle & Memory
                </h4>
                <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1.5">
                  <div className="font-semibold text-[#f7f5f0]">Synopsis:</div>
                  <p className="text-[#b0a89f] leading-relaxed">{parsedJson.chapter_summary}</p>
                </div>

                {parsedJson.character_status_updates && (
                  <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1.5">
                    <div className="font-semibold text-[#f7f5f0]">Character Status Updates:</div>
                    <div className="space-y-1 font-mono text-[11px]">
                      {Object.entries(parsedJson.character_status_updates).map(([char, status], i) => (
                        <div key={i} className="text-[#b0a89f]">
                          <span className="font-medium text-[#d9a05b]">{char}: </span>
                          <span className="text-[#857d75]">{String(status)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {parsedJson.new_foreshadowing_flags && (
                  <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs space-y-1">
                    <div className="font-semibold text-[#f7f5f0]">Foreshadowing & Continuity Flags:</div>
                    <ul className="list-disc list-inside text-[#857d75] space-y-0.5">
                      {parsedJson.new_foreshadowing_flags.map((flag: string, i: number) => (
                        <li key={i}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* 4. Generic / Raw JSON Pretty Print */}
            {!parsedJson.new_characters && !parsedJson.critique_notes && !parsedJson.chapter_summary && (
              <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[3px] p-4">
                <pre className="font-mono text-xs text-[#b0a89f] whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(parsedJson, null, 2)}
                </pre>
              </div>
            )}

            {/* Optional Postscript Text */}
            {extracted?.postscript && (
              <div className="p-3 rounded-[3px] bg-[#2b2622] border border-[#3f3a36] text-xs text-[#857d75] flex items-start gap-2 italic">
                <MessageSquare className="w-4 h-4 text-[#857d75] shrink-0 mt-0.5" />
                <div>{extracted.postscript}</div>
              </div>
            )}
          </div>
        ) : (
          /* Rich Literary Prose View with Paragraphs */
          <div className="max-w-3xl mx-auto font-serif text-[#f7f5f0] text-base leading-loose space-y-4">
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
