/**
 * Utilities for extracting and parsing JSON from arbitrary text or markdown code blocks.
 */

export interface ExtractedJsonResult {
  parsed: any;
  preamble?: string;
  postscript?: string;
}

/**
 * Attempt to extract and parse JSON from raw agent output.
 * Handles:
 * 1. Plain JSON string (`{ ... }` or `[ ... ]`)
 * 2. Markdown fenced code blocks (` ```json ... ``` ` or ` ``` ... ``` `)
 * 3. Text containing embedded JSON with conversational preamble or postscript
 */
export function extractJsonFromText(text: string): ExtractedJsonResult | null {
  if (!text || typeof text !== 'string') return null;
  const trimmed = text.trim();
  if (!trimmed) return null;

  // 1. Direct JSON parse (fast path)
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed === 'object' && parsed !== null) {
        return { parsed };
      }
    } catch {
      // Continue to regex extraction if there are trailing syntax errors or fences
    }
  }

  // 2. Fenced code block: ```json ... ``` or ``` ... ```
  const codeBlockRegex = /```(?:json)?\s*\n?([\s\S]*?)\n?```/i;
  const match = trimmed.match(codeBlockRegex);
  if (match && match[1]) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (typeof parsed === 'object' && parsed !== null) {
        const preamble = match.index ? trimmed.substring(0, match.index).trim() : undefined;
        const matchEnd = (match.index || 0) + match[0].length;
        const postscript = matchEnd < trimmed.length ? trimmed.substring(matchEnd).trim() : undefined;
        return {
          parsed,
          preamble: preamble || undefined,
          postscript: postscript || undefined,
        };
      }
    } catch {
      // Continue to outer brace search
    }
  }

  // 3. Search for outermost balanced curly braces { ... } or brackets [ ... ]
  const firstBrace = trimmed.indexOf('{');
  const firstBracket = trimmed.indexOf('[');
  let startIdx = -1;
  let endChar = '';

  if (firstBrace !== -1 && (firstBracket === -1 || firstBrace < firstBracket)) {
    startIdx = firstBrace;
    endChar = '}';
  } else if (firstBracket !== -1) {
    startIdx = firstBracket;
    endChar = ']';
  }

  if (startIdx !== -1) {
    const lastIdx = trimmed.lastIndexOf(endChar);
    if (lastIdx > startIdx) {
      const candidate = trimmed.slice(startIdx, lastIdx + 1);
      try {
        const parsed = JSON.parse(candidate);
        if (typeof parsed === 'object' && parsed !== null) {
          const preamble = trimmed.substring(0, startIdx).trim();
          const postscript = trimmed.substring(lastIdx + 1).trim();
          return {
            parsed,
            preamble: preamble || undefined,
            postscript: postscript || undefined,
          };
        }
      } catch {
        // Fall through
      }
    }
  }

  return null;
}

/**
 * Clean a preview string for timeline display by removing markdown code block markers.
 */
export function cleanPreviewSnippet(text: string): string {
  if (!text) return '';
  let cleaned = text.trim();

  // Strip leading ```json or ```
  cleaned = cleaned.replace(/^```(?:json)?\s*\n?/i, '');
  // Strip trailing ```
  cleaned = cleaned.replace(/\n?```$/i, '');

  return cleaned.trim();
}
