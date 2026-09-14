/**
 * LLM Model Pricing and Token Cost Calculation Engine.
 *
 * Rates are calibrated in USD per 1,000,000 tokens ($/M) based on official
 * provider documentation (Google Gemini, OpenAI, Anthropic).
 */

export interface ModelPricing {
  provider: string;
  name: string;
  description?: string;
  inputPerMillion: number;       // $/1M uncached input tokens
  cachedInputPerMillion: number; // $/1M cached input tokens (e.g. Gemini KV Context Cache)
  outputPerMillion: number;      // $/1M output tokens (also applies to thought/reasoning tokens)
}

export interface CostBreakdown {
  freshInputCost: number;
  cachedInputCost: number;
  outputCost: number;
  thoughtCost: number;
  totalCost: number;
  savingsFromCache: number;
  formattedTotal: string;
  formattedSavings: string;
}

/**
 * Standard pricing catalog across known models.
 */
export const MODEL_PRICING_CATALOG: Record<string, ModelPricing> = {
  // Google Gemini 3.5 Flash-Lite
  'gemini-3.5-flash-lite': {
    provider: 'Google Gemini',
    name: 'Gemini 3.5 Flash Lite',
    description: 'Newest hyper-fast, low-cost tier',
    inputPerMillion: 0.30,
    cachedInputPerMillion: 0.075,
    outputPerMillion: 2.50,
  },
  // Google Gemini 3.1 Flash-Lite
  'gemini-3.1-flash-lite': {
    provider: 'Google Gemini',
    name: 'Gemini 3.1 Flash Lite',
    description: 'Optimized for simple classification & extraction tasks',
    inputPerMillion: 0.25,
    cachedInputPerMillion: 0.0625,
    outputPerMillion: 1.50,
  },
  // Google Gemini 2.5 Flash-Lite
  'gemini-2.5-flash-lite': {
    provider: 'Google Gemini',
    name: 'Gemini 2.5 Flash Lite',
    description: 'The cheapest paid tier option available',
    inputPerMillion: 0.10,
    cachedInputPerMillion: 0.025,
    outputPerMillion: 0.40,
  },
  // Google Gemini Flash
  'gemini-2.5-flash': {
    provider: 'Google Gemini',
    name: 'Gemini 2.5 Flash',
    inputPerMillion: 0.075,
    cachedInputPerMillion: 0.01875,
    outputPerMillion: 0.30,
  },
  'gemini-1.5-flash': {
    provider: 'Google Gemini',
    name: 'Gemini 1.5 Flash',
    inputPerMillion: 0.075,
    cachedInputPerMillion: 0.01875,
    outputPerMillion: 0.30,
  },
  // Google Gemini Pro
  'gemini-2.5-pro': {
    provider: 'Google Gemini',
    name: 'Gemini 2.5 Pro',
    inputPerMillion: 1.25,
    cachedInputPerMillion: 0.3125,
    outputPerMillion: 5.00,
  },
  'gemini-1.5-pro': {
    provider: 'Google Gemini',
    name: 'Gemini 1.5 Pro',
    inputPerMillion: 1.25,
    cachedInputPerMillion: 0.3125,
    outputPerMillion: 5.00,
  },
  // Google Gemma Open Models
  'gemma-4-26b-a4b-it': {
    provider: 'Google Gemma',
    name: 'Gemma 4 26B A4B IT',
    inputPerMillion: 0.10,
    cachedInputPerMillion: 0.025,
    outputPerMillion: 0.20,
  },
  'gemma-2-27b-it': {
    provider: 'Google Gemma',
    name: 'Gemma 2 27B IT',
    inputPerMillion: 0.10,
    cachedInputPerMillion: 0.025,
    outputPerMillion: 0.20,
  },
  'gemma-2-9b-it': {
    provider: 'Google Gemma',
    name: 'Gemma 2 9B IT',
    inputPerMillion: 0.06,
    cachedInputPerMillion: 0.015,
    outputPerMillion: 0.12,
  },
  // OpenAI
  'gpt-4o-mini': {
    provider: 'OpenAI',
    name: 'GPT-4o Mini',
    inputPerMillion: 0.15,
    cachedInputPerMillion: 0.075,
    outputPerMillion: 0.60,
  },
  'gpt-4o': {
    provider: 'OpenAI',
    name: 'GPT-4o',
    inputPerMillion: 2.50,
    cachedInputPerMillion: 1.25,
    outputPerMillion: 10.00,
  },
  'o1-mini': {
    provider: 'OpenAI',
    name: 'o1-mini',
    inputPerMillion: 1.10,
    cachedInputPerMillion: 0.55,
    outputPerMillion: 4.40,
  },
  // Anthropic
  'claude-3-5-haiku': {
    provider: 'Anthropic',
    name: 'Claude 3.5 Haiku',
    inputPerMillion: 0.80,
    cachedInputPerMillion: 0.08,
    outputPerMillion: 4.00,
  },
  'claude-3-5-sonnet': {
    provider: 'Anthropic',
    name: 'Claude 3.5 Sonnet',
    inputPerMillion: 3.00,
    cachedInputPerMillion: 0.30,
    outputPerMillion: 15.00,
  },
  'claude-3-7-sonnet': {
    provider: 'Anthropic',
    name: 'Claude 3.7 Sonnet',
    inputPerMillion: 3.00,
    cachedInputPerMillion: 0.30,
    outputPerMillion: 15.00,
  },
  // Mock / Test Models
  'mock-novel-llm': {
    provider: 'Local Mock',
    name: 'Mock Novel LLM',
    inputPerMillion: 0.0,
    cachedInputPerMillion: 0.0,
    outputPerMillion: 0.0,
  },
};

/**
 * Resolve pricing for any model name via fuzzy matching or fallbacks.
 */
export function getModelPricing(modelName: string): ModelPricing {
  if (!modelName) {
    return {
      provider: 'Standard LLM',
      name: 'Standard Model',
      inputPerMillion: 0.10,
      cachedInputPerMillion: 0.025,
      outputPerMillion: 0.40,
    };
  }

  const raw = modelName.trim().toLowerCase();

  // Exact match
  if (MODEL_PRICING_CATALOG[raw]) {
    return MODEL_PRICING_CATALOG[raw];
  }

  // Mock / offline testing
  if (raw.includes('mock') || raw.includes('test')) {
    return {
      provider: 'Local Mock',
      name: modelName,
      inputPerMillion: 0.0,
      cachedInputPerMillion: 0.0,
      outputPerMillion: 0.0,
    };
  }

  // Gemini family
  if (raw.includes('gemini')) {
    if (raw.includes('3.5-flash-lite') || (raw.includes('3.5') && raw.includes('lite'))) {
      return MODEL_PRICING_CATALOG['gemini-3.5-flash-lite'];
    }
    if (raw.includes('3.1-flash-lite') || (raw.includes('3.1') && raw.includes('lite'))) {
      return MODEL_PRICING_CATALOG['gemini-3.1-flash-lite'];
    }
    if (raw.includes('2.5-flash-lite') || (raw.includes('2.5') && raw.includes('lite')) || raw.includes('flash-lite')) {
      return MODEL_PRICING_CATALOG['gemini-2.5-flash-lite'];
    }
    if (raw.includes('pro')) {
      return {
        provider: 'Google Gemini',
        name: modelName,
        inputPerMillion: 1.25,
        cachedInputPerMillion: 0.3125,
        outputPerMillion: 5.00,
      };
    }
    // General flash variants
    return {
      provider: 'Google Gemini',
      name: modelName,
      inputPerMillion: 0.15,
      cachedInputPerMillion: 0.0375,
      outputPerMillion: 0.60,
    };
  }

  // Gemma family
  if (raw.includes('gemma')) {
    return {
      provider: 'Google Gemma',
      name: modelName,
      inputPerMillion: 0.10,
      cachedInputPerMillion: 0.025,
      outputPerMillion: 0.20,
    };
  }

  // OpenAI family
  if (raw.includes('gpt-4o-mini') || raw.includes('mini')) {
    return {
      provider: 'OpenAI',
      name: modelName,
      inputPerMillion: 0.15,
      cachedInputPerMillion: 0.075,
      outputPerMillion: 0.60,
    };
  }
  if (raw.includes('gpt-4o') || raw.includes('gpt-4')) {
    return {
      provider: 'OpenAI',
      name: modelName,
      inputPerMillion: 2.50,
      cachedInputPerMillion: 1.25,
      outputPerMillion: 10.00,
    };
  }

  // Anthropic family
  if (raw.includes('haiku')) {
    return {
      provider: 'Anthropic',
      name: modelName,
      inputPerMillion: 0.80,
      cachedInputPerMillion: 0.08,
      outputPerMillion: 4.00,
    };
  }
  if (raw.includes('claude') || raw.includes('sonnet')) {
    return {
      provider: 'Anthropic',
      name: modelName,
      inputPerMillion: 3.00,
      cachedInputPerMillion: 0.30,
      outputPerMillion: 15.00,
    };
  }

  // Default fallback
  return {
    provider: 'Standard LLM',
    name: modelName,
    inputPerMillion: 0.10,
    cachedInputPerMillion: 0.025,
    outputPerMillion: 0.40,
  };
}

/**
 * Format token cost into human-readable currency representation ($).
 */
export function formatCost(cost: number): string {
  if (!cost || cost <= 0) return '$0.00';
  if (cost < 0.0001) return `< $0.0001`;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  if (cost < 1) return `$${cost.toFixed(3)}`;
  return `$${cost.toFixed(2)}`;
}

/**
 * Format micro costs (for individual token component chips).
 */
export function formatMicroCost(cost: number): string {
  if (!cost || cost <= 0) return '$0.00';
  if (cost < 0.00001) return `< $0.00001`;
  if (cost < 0.001) return `$${cost.toFixed(5)}`;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(3)}`;
}

/**
 * Calculate token expenditures and KV cache savings.
 */
export function calculateCost(
  usage: {
    input_tokens?: number;
    cached_tokens?: number;
    output_tokens?: number;
    thought_tokens?: number;
  },
  modelName: string
): CostBreakdown {
  const pricing = getModelPricing(modelName);

  const totalInput = usage.input_tokens || 0;
  const cached = Math.min(totalInput, usage.cached_tokens || 0);
  const freshInput = Math.max(0, totalInput - cached);
  const output = usage.output_tokens || 0;
  const thought = usage.thought_tokens || 0;

  const freshInputCost = (freshInput * pricing.inputPerMillion) / 1_000_000;
  const cachedInputCost = (cached * pricing.cachedInputPerMillion) / 1_000_000;
  const outputCost = (output * pricing.outputPerMillion) / 1_000_000;
  const thoughtCost = (thought * pricing.outputPerMillion) / 1_000_000;

  const totalCost = freshInputCost + cachedInputCost + outputCost + thoughtCost;

  // Potential cost if cached tokens were charged at full uncached input rate
  const fullPriceForCached = (cached * pricing.inputPerMillion) / 1_000_000;
  const savingsFromCache = Math.max(0, fullPriceForCached - cachedInputCost);

  return {
    freshInputCost,
    cachedInputCost,
    outputCost,
    thoughtCost,
    totalCost,
    savingsFromCache,
    formattedTotal: formatCost(totalCost),
    formattedSavings: formatCost(savingsFromCache),
  };
}
