/**
 * Multilingual token estimation utilities for LLM prompts and outputs.
 */

/**
 * Estimates token count for multilingual text (English, Japanese, Thai, Chinese, Code).
 *
 * Rules of thumb in modern LLM tokenizers (tiktoken / SentencePiece / Gemini):
 * - ASCII/Latin text: ~4 characters per token
 * - CJK characters (Japanese Kanji/Kana, Hanzi, Hangul): ~1.2 to 1.5 tokens per character
 * - Thai characters (\u0e00-\u0e7f): ~1.3 to 1.5 tokens per character
 * - Whitespace & symbols: ~1 token per 3-4 characters
 */
export function estimateTokens(text: string): number {
  if (!text || typeof text !== 'string') return 0;
  if (text.length === 0) return 0;

  // Count CJK characters
  const cjkMatches = text.match(
    /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f\uac00-\ud7af]/g
  );
  const cjkCount = cjkMatches ? cjkMatches.length : 0;

  // Count Thai characters
  const thaiMatches = text.match(/[\u0e00-\u0e7f]/g);
  const thaiCount = thaiMatches ? thaiMatches.length : 0;

  // Remaining characters (mostly Latin, ASCII, numbers, punctuation, spaces)
  const otherCount = Math.max(0, text.length - cjkCount - thaiCount);

  // Weighted calculation:
  // - CJK: ~1.3 tokens/char
  // - Thai: ~1.4 tokens/char
  // - Other: 1 token per 4 chars (0.25)
  const estimated = Math.ceil(cjkCount * 1.3 + thaiCount * 1.4 + otherCount / 4);
  return Math.max(1, estimated);
}

export interface PromptTokenStats {
  systemTokens: number;
  userTokens: number;
  totalTokens: number;
  isMeasured: boolean;
}

/**
 * Given system prompt, user prompt, and total actual input_tokens from the API,
 * compute calibrated token allocations for system and user prompts.
 */
export function getPromptTokenStats(
  systemPrompt: string,
  userPrompt: string,
  measuredInputTokens?: number
): PromptTokenStats {
  const sysRaw = estimateTokens(systemPrompt);
  const userRaw = estimateTokens(userPrompt);
  const rawSum = sysRaw + userRaw;

  // If the model provider recorded exact measured input tokens
  if (measuredInputTokens && measuredInputTokens > 0 && rawSum > 0) {
    const sysRatio = sysRaw / rawSum;
    const systemTokens = Math.round(measuredInputTokens * sysRatio);
    const userTokens = Math.max(1, measuredInputTokens - systemTokens);
    return {
      systemTokens,
      userTokens,
      totalTokens: measuredInputTokens,
      isMeasured: true,
    };
  }

  return {
    systemTokens: sysRaw,
    userTokens: userRaw,
    totalTokens: rawSum,
    isMeasured: false,
  };
}
