import React, { useState, useEffect } from 'react';
import { getVersion } from '@tauri-apps/api/app';
import { invoke } from '@tauri-apps/api/core';
import { check, type Update } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';
import {
  Settings,
  Cpu,
  RefreshCw,
  Layers,
  Save,
  Check,
  Folder,
  Sliders,
  Download,
  RotateCcw,
  Bot,
  Sparkles,
  X,
  BookMarked,
  ShieldAlert,
  Zap,
  LayoutGrid,
  Search,
  Info,
  KeyRound,
  DownloadCloud,
  FileText,
  FolderOpen,
} from 'lucide-react';
import { isTauriDesktopRuntime } from '../services/apiBase';
import {
  GenerationRole,
  GenerationSettings,
  MachineEnvironment,
  ModelCatalogResult,
  ModelProvider,
  ProjectSettings,
  UpdateCheckResult,
  LogsInfoResult,
} from '../types/dashboard';
import {
  checkLatestRelease,
  fetchMachineEnvironment,
  fetchModelCatalog,
  fetchSettings,
  saveMachineEnvironment,
  updateSettings,
  fetchLogsInfo,
  openLogsDirectory,
} from '../services/dashboardApi';

const isTauriDesktop = isTauriDesktopRuntime;
const isLocalUpdaterTest = import.meta.env.VITE_LOCAL_UPDATER_TEST === 'true';

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  if (typeof error === 'object' && error !== null) {
    const message = 'message' in error ? error.message : undefined;
    if (typeof message === 'string' && message.trim()) return message;
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== '{}') return serialized;
    } catch {
      // Keep the fallback if the thrown value cannot be serialized.
    }
  }
  return fallback;
};

interface SettingsViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
  onProjectUpdated?: () => void;
}

interface SettingCategory {
  id: string;
  name: string;
  shortDesc: string;
  icon: React.ElementType;
  group: 'global' | 'project';
}

const SETTING_CATEGORIES: SettingCategory[] = [
  { id: 'global', name: 'Environment & API Keys', shortDesc: 'Machine-wide .env defaults', icon: KeyRound, group: 'global' },
  { id: 'updates', name: 'App Updates', shortDesc: 'Install updates in the app', icon: Download, group: 'global' },
  { id: 'logs', name: 'Logs & Diagnostics', shortDesc: 'Local application log files', icon: FileText, group: 'global' },
  { id: 'all', name: 'All Project Settings', shortDesc: 'Full project configuration', icon: LayoutGrid, group: 'project' },
  { id: 'general', name: 'Novel Information', shortDesc: 'Metadata, title & language', icon: Sliders, group: 'project' },
  { id: 'models', name: 'Model Routing', shortDesc: 'Agent models & LLM cascades', icon: Cpu, group: 'project' },
  { id: 'review', name: 'Review & Quality', shortDesc: 'Reflection loops & Diff patch', icon: RefreshCw, group: 'project' },
  { id: 'chunking', name: 'Semantic Chunking', shortDesc: 'Line-based text chunking', icon: Layers, group: 'project' },
  { id: 'memory', name: 'Memory & Bible', shortDesc: 'Cross-folder & reconciliation', icon: BookMarked, group: 'project' },
  { id: 'rag', name: 'Episodic Lore & RAG', shortDesc: 'Tier 4 SQLite hybrid retrieval', icon: Sparkles, group: 'project' },
  { id: 'safety', name: 'Safety & Bisection', shortDesc: 'Recursive safety bisection', icon: ShieldAlert, group: 'project' },
  { id: 'ratelimit', name: 'Rate Limits & Quota', shortDesc: '32k TPM / 60 RPM guard', icon: Zap, group: 'project' },
  { id: 'paths', name: 'Workspace Paths', shortDesc: 'Raw & translated directories', icon: Folder, group: 'project' },
];

interface GlobalEnvGroup {
  title: string;
  description?: string;
  keys: string[];
  agent?: boolean;
}

const GLOBAL_ENV_GROUPS: Record<string, GlobalEnvGroup> = {
  general: { title: 'Language Defaults', keys: ['SOURCE_LANG', 'TARGET_LANG'] },
  models: {
    title: 'Shared Model Defaults',
    description: 'Primary, fallback, and shared generation defaults for machine-wide projects.',
    keys: [
      'DEFAULT_MODEL', 'NOVEL_MODEL', 'NOVEL_FALLBACK_MODEL',
      'NOVEL_TEMPERATURE', 'NOVEL_THINKING_LEVEL', 'NOVEL_THINKING_BUDGET', 'NOVEL_USE_INTERACTIONS',
    ],
  },
  agent_extractor: {
    title: 'Entity Extractor',
    description: 'Stage 1 · Finds characters and terminology before drafting.',
    keys: ['NOVEL_EXTRACTOR_MODEL', 'NOVEL_EXTRACTOR_TEMPERATURE', 'NOVEL_EXTRACTOR_THINKING_LEVEL', 'NOVEL_EXTRACTOR_THINKING_BUDGET', 'NOVEL_EXTRACTOR_USE_INTERACTIONS'],
    agent: true,
  },
  agent_drafter: {
    title: 'Context-Aware Drafter',
    description: 'Stage 2 · Produces the initial literary translation.',
    keys: ['NOVEL_DRAFTER_MODEL', 'NOVEL_DRAFTER_TEMPERATURE', 'NOVEL_DRAFTER_THINKING_LEVEL', 'NOVEL_DRAFTER_THINKING_BUDGET', 'NOVEL_DRAFTER_USE_INTERACTIONS'],
    agent: true,
  },
  agent_critic: {
    title: 'Critique Agent',
    description: 'Stage 3 · Audits fidelity, style, omissions, and terminology.',
    keys: ['NOVEL_CRITIC_MODEL', 'NOVEL_CRITIC_TEMPERATURE', 'NOVEL_CRITIC_THINKING_LEVEL', 'NOVEL_CRITIC_THINKING_BUDGET', 'NOVEL_CRITIC_USE_INTERACTIONS'],
    agent: true,
  },
  agent_polisher: {
    title: 'Polishing Agent',
    description: 'Stage 4 · Refines the draft into publication-ready prose.',
    keys: ['NOVEL_POLISHER_MODEL', 'NOVEL_POLISHER_TEMPERATURE', 'NOVEL_POLISHER_THINKING_LEVEL', 'NOVEL_POLISHER_THINKING_BUDGET', 'NOVEL_POLISHER_USE_INTERACTIONS'],
    agent: true,
  },
  agent_chronicler: {
    title: 'Chronicler Agent',
    description: 'Stage 5 · Updates summaries, continuity, and series memory.',
    keys: ['NOVEL_CHRONICLER_MODEL', 'NOVEL_CHRONICLER_TEMPERATURE', 'NOVEL_CHRONICLER_THINKING_LEVEL', 'NOVEL_CHRONICLER_THINKING_BUDGET', 'NOVEL_CHRONICLER_USE_INTERACTIONS'],
    agent: true,
  },
  agent_scraper: {
    title: 'Novel Scraper',
    description: 'Separate route and generation settings for URL chapter extraction.',
    keys: ['NOVEL_SCRAPER_MODEL', 'NOVEL_SCRAPER_TEMPERATURE', 'NOVEL_SCRAPER_THINKING_LEVEL', 'NOVEL_SCRAPER_THINKING_BUDGET', 'NOVEL_SCRAPER_USE_INTERACTIONS'],
    agent: true,
  },
  review: { title: 'Quality Defaults', keys: ['NOVEL_MAX_REVIEW_LOOPS', 'NOVEL_QUALITY_THRESHOLD'] },
  memory: {
    title: 'Memory & Entity Defaults',
    keys: ['NOVEL_FILTER_EXTRACTOR_ENTITIES', 'NOVEL_POST_POLISH_RECONCILIATION'],
  },
  rag: { title: 'RAG Model Defaults', keys: ['NOVEL_RAG_EMBEDDING_MODEL', 'NOVEL_RAG_RERANKER_MODEL'] },
  ratelimit: { title: 'Rate Limit Defaults', keys: ['NOVEL_MAX_TPM', 'NOVEL_MAX_RPM'] },
  paths: {
    title: 'Workspace Defaults',
    keys: ['NOVEL_PROJECTS_DIR', 'NOVEL_SCRAPER_PATH', 'NOVEL_SCRAPER_PYTHON'],
  },
};

const GLOBAL_ENV_ENTRIES = Object.entries(GLOBAL_ENV_GROUPS);
const FIRST_AGENT_ENV_GROUP_INDEX = GLOBAL_ENV_ENTRIES.findIndex(([, group]) => group.agent);
const AGENT_ENV_GROUPS = GLOBAL_ENV_ENTRIES.filter(([, group]) => group.agent);

const GLOBAL_ENV_LABELS: Record<string, string> = {
  DEFAULT_MODEL: 'Default model',
  NOVEL_MODEL: 'Primary model',
  NOVEL_FALLBACK_MODEL: 'Fallback model',
  NOVEL_SCRAPER_MODEL: 'Novel scraper model (blank inherits primary)',
  NOVEL_THINKING_LEVEL: 'Default thinking level',
  NOVEL_THINKING_BUDGET: 'Default thinking budget',
  NOVEL_TEMPERATURE: 'Generation temperature',
  NOVEL_USE_INTERACTIONS: 'Use Gemini Interactions API',
};

const AGENT_ENV_LABELS: Record<string, string> = {
  MODEL: 'Model',
  TEMPERATURE: 'Temperature',
  THINKING_LEVEL: 'Thinking level',
  THINKING_BUDGET: 'Thinking budget',
  USE_INTERACTIONS: 'Use Gemini Interactions API',
};

const GENERATION_ROLES: { role: GenerationRole; title: string; stage: string; description: string; modelKey: keyof ProjectSettings; effectiveModelKey: keyof ProjectSettings }[] = [
  { role: 'extractor', title: 'Entity Extractor', stage: 'Stage 1', description: 'Finds characters and terminology before drafting.', modelKey: 'extractor_model', effectiveModelKey: 'effective_extractor_model' },
  { role: 'drafter', title: 'Context-Aware Drafter', stage: 'Stage 2', description: 'Produces the initial literary translation.', modelKey: 'drafter_model', effectiveModelKey: 'effective_drafter_model' },
  { role: 'critic', title: 'Critique Agent', stage: 'Stage 3', description: 'Audits fidelity, style, omissions, and terminology.', modelKey: 'critic_model', effectiveModelKey: 'effective_critic_model' },
  { role: 'polisher', title: 'Polishing Agent', stage: 'Stage 4', description: 'Refines the draft into publication-ready prose.', modelKey: 'polisher_model', effectiveModelKey: 'effective_polisher_model' },
  { role: 'chronicler', title: 'Chronicler Agent', stage: 'Stage 5', description: 'Updates summaries, continuity, and series memory.', modelKey: 'chronicler_model', effectiveModelKey: 'effective_chronicler_model' },
  { role: 'scraper', title: 'Novel Scraper', stage: 'Separate route', description: 'Extracts chapter text from supported novel websites.', modelKey: 'scraper_model', effectiveModelKey: 'effective_scraper_model' },
];

const MODEL_INPUT_CLASS = 'w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500';

const providerForRoute = (route: string): ModelProvider =>
  route.startsWith('openai:') ? 'openai'
    : route.startsWith('openrouter:') ? 'openrouter'
      : route.startsWith('custom:') ? 'custom' : 'gemini';

const modelIdForRoute = (route: string): string =>
  route.startsWith('openai:') || route.startsWith('openrouter:') || route.startsWith('custom:')
    ? route.slice(route.indexOf(':') + 1) : route;

const isOpenAIReasoningModel = (provider: ModelProvider | 'all', model: string): boolean => {
  const normalized = model.trim().replace(/^openai\//i, '');
  if (provider === 'openai' || provider === 'custom') return /^(?:o1|o3|o4)(?:$|-)/i.test(normalized);
  return provider === 'openrouter' && /^openai\/(?:o1|o3|o4)(?:$|-)/i.test(model.trim());
};

interface ModelRouteControlProps {
  label: string;
  value: string;
  effectiveValue?: string;
  onChange: (value: string) => void;
  catalogs: Partial<Record<ModelProvider, ModelCatalogResult>>;
  loadingCatalogs: Partial<Record<ModelProvider, boolean>>;
  catalogErrors: Partial<Record<ModelProvider, string>>;
  apiKeyStatus?: Record<string, boolean>;
  customBaseUrl?: string;
  onLoadCatalog: (provider: ModelProvider) => void;
  inherit?: boolean;
}

const ModelRouteControl: React.FC<ModelRouteControlProps> = ({
  label, value, effectiveValue, onChange, catalogs, loadingCatalogs, catalogErrors, apiKeyStatus, customBaseUrl, onLoadCatalog, inherit,
}) => {
  const [providerOverride, setProviderOverride] = useState<ModelProvider | null>(null);
  const provider = providerOverride || providerForRoute(value || effectiveValue || '');
  const catalog = catalogs[provider];
  const catalogLoading = Boolean(loadingCatalogs[provider]);
  const catalogError = catalogErrors[provider];
  const configured = catalog?.configured ?? (provider === 'gemini'
    ? apiKeyStatus?.GEMINI_API_KEY || apiKeyStatus?.GOOGLE_API_KEY
    : provider === 'openai'
      ? apiKeyStatus?.OPENAI_API_KEY
      : provider === 'openrouter'
        ? apiKeyStatus?.OPENROUTER_API_KEY
        : Boolean(apiKeyStatus?.CUSTOM_API_KEY && customBaseUrl?.trim()));
  const listId = React.useId();

  useEffect(() => {
    if (value) setProviderOverride(null);
  }, [value]);

  const updateModel = (model: string) => {
    const modelId = model.trim().replace(new RegExp(`^${provider}:`), '');
    onChange(modelId ? (provider === 'gemini' ? modelId : `${provider}:${modelId}`) : '');
    if (modelId) setProviderOverride(null);
  };

  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <label className="font-semibold text-slate-200">{label}</label>
        {inherit && (value ? (
          <button type="button" onClick={() => { setProviderOverride(null); onChange(''); }} className="text-[10px] text-amber-300 hover:text-amber-200">Clear override</button>
        ) : <span className="text-emerald-300">Inheriting global default</span>)}
      </div>
      <div className="grid grid-cols-[minmax(110px,0.45fr)_minmax(0,1fr)] gap-2">
        <select
          aria-label={`${label} provider`}
          value={provider}
          onChange={(event) => {
            const nextProvider = event.target.value as ModelProvider;
            setProviderOverride(nextProvider);
            onChange('');
          }}
          className={MODEL_INPUT_CLASS}
        >
          <option value="gemini">Gemini</option>
          <option value="openai">OpenAI</option>
          <option value="openrouter">OpenRouter</option>
          <option value="custom">Custom OpenAI-compatible</option>
        </select>
        <input
          type="text"
          list={listId}
          aria-label={`${label} model ID`}
          value={modelIdForRoute(value)}
          onChange={(event) => updateModel(event.target.value)}
          placeholder={effectiveValue && (!providerOverride || providerForRoute(effectiveValue) === provider) ? modelIdForRoute(effectiveValue) : 'Search catalog or enter a model ID'}
          className={MODEL_INPUT_CLASS}
        />
      </div>
      <datalist id={listId}>
        {catalog?.models.map((model) => <option key={model} value={model} />)}
      </datalist>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
        <span className="text-slate-500">
          {value ? `Route: ${value}` : effectiveValue ? `Effective: ${effectiveValue}` : 'Enter a model ID or inherit the configured default.'}
        </span>
        <button type="button" onClick={() => onLoadCatalog(provider)} disabled={catalogLoading} className="text-indigo-300 hover:text-indigo-200 disabled:opacity-50">
          {catalogLoading ? 'Loading catalog…' : catalog ? `Refresh ${provider} catalog (${catalog.models.length})` : `Load ${provider} catalog`}
        </button>
      </div>
      {configured === false && <p className="text-amber-300">{provider === 'custom' ? 'Configure CUSTOM_API_KEY and CUSTOM_API_BASE_URL in global settings.' : `No ${provider} API key is configured. You can still enter a model ID and save it after adding a key.`}</p>}
      {catalogError && <p role="alert" className="text-rose-300">{catalogError}</p>}
    </div>
  );
};

interface GenerationSettingsEditorProps {
  role: GenerationRole | 'default';
  provider: ModelProvider | 'all';
  model?: string;
  projectValue?: GenerationSettings;
  effectiveValue?: GenerationSettings;
  environmentValues?: Record<string, string>;
  onProjectChange?: (value: GenerationSettings) => void;
  onEnvironmentChange?: (key: string, value: string) => void;
}

const GenerationSettingsEditor: React.FC<GenerationSettingsEditorProps> = ({
  role, provider, model = '', projectValue, effectiveValue, environmentValues, onProjectChange, onEnvironmentChange,
}) => {
  const isProject = Boolean(onProjectChange);
  const prefix = role === 'default' ? 'NOVEL' : `NOVEL_${role.toUpperCase()}`;
  const interactionKey = role === 'default' ? 'NOVEL_USE_INTERACTIONS' : `${prefix}_USE_INTERACTIONS`;
  const environmentKey = (field: keyof GenerationSettings) => field === 'use_interactions_api'
    ? interactionKey
    : `${prefix}_${field === 'thinking_level' ? 'THINKING_LEVEL' : field === 'thinking_budget' ? 'THINKING_BUDGET' : 'TEMPERATURE'}`;
  const current = (field: keyof GenerationSettings): string => {
    if (!isProject) {
      const value = environmentValues?.[environmentKey(field)] || '';
      if (field === 'use_interactions_api' && value) {
        return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase()) ? 'true' : 'false';
      }
      return value;
    }
    const value = projectValue?.[field];
    return value === null || value === undefined ? '' : String(value);
  };
  const inherited = (field: keyof GenerationSettings): string => {
    const value = effectiveValue?.[field];
    return value === null || value === undefined ? '' : String(value);
  };
  const update = (field: keyof GenerationSettings, value: string) => {
    if (isProject) {
      const parsed: GenerationSettings[keyof GenerationSettings] = value === ''
        ? null
        : field === 'temperature' || field === 'thinking_budget'
          ? Number(value)
          : field === 'use_interactions_api'
            ? value === 'true'
            : value;
      onProjectChange?.({ ...projectValue, [field]: parsed });
    } else {
      onEnvironmentChange?.(environmentKey(field), value);
    }
  };
  const showGeminiControls = provider === 'gemini' || provider === 'all';
  const showTemperature = !isOpenAIReasoningModel(provider, model);
  const interactionSetting = current('use_interactions_api')
    || (isProject ? inherited('use_interactions_api') : environmentValues?.NOVEL_USE_INTERACTIONS || '');
  const interactionsEnabled = interactionSetting
    ? ['1', 'true', 'yes', 'on'].includes(interactionSetting.toLowerCase())
    : true;
  const inputClass = 'w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 focus:outline-none focus:border-indigo-500';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
      {showTemperature ? <label className="block">
        <span className="block text-slate-400 mb-1 font-medium">Temperature</span>
        <input type="number" min="0" max="2" step="0.1" value={current('temperature')} placeholder={inherited('temperature') || 'Provider default'} onChange={(event) => update('temperature', event.target.value)} className={inputClass} />
      </label> : <p className="self-center text-slate-500">Temperature is not supported by this model; saved values are preserved.</p>}
      {showGeminiControls && <>
        <label className="block">
          <span className="block text-slate-400 mb-1 font-medium">Thinking level</span>
          <select value={current('thinking_level')} onChange={(event) => update('thinking_level', event.target.value)} className={inputClass}>
            <option value="">{isProject ? `Inherit${inherited('thinking_level') ? ` (${inherited('thinking_level')})` : ''}` : 'Provider default'}</option>
            {!['minimal', 'low', 'medium', 'high'].includes(current('thinking_level')) && current('thinking_level') && <option value={current('thinking_level')}>{current('thinking_level')}</option>}
            <option value="minimal">Minimal</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>
        {!interactionsEnabled && <label className="block">
          <span className="block text-slate-400 mb-1 font-medium">Thinking budget</span>
          <input type="number" min="0" step="1" value={current('thinking_budget')} placeholder={inherited('thinking_budget') || 'Provider default'} onChange={(event) => update('thinking_budget', event.target.value)} className={inputClass} />
        </label>}
        <label className="sm:col-span-2 flex items-center justify-between gap-3 rounded-[3px] border border-[#3f3a36] bg-[#24201d] p-2">
          <span className="text-slate-400">Gemini Interactions API</span>
          <select aria-label="Gemini Interactions API" value={current('use_interactions_api')} onChange={(event) => update('use_interactions_api', event.target.value)} className="bg-[#2b2622] border border-[#3f3a36] rounded px-2 py-1 text-slate-200">
            <option value="">{isProject ? `Inherit${inherited('use_interactions_api') ? ` (${inherited('use_interactions_api') === 'true' ? 'On' : 'Off'})` : ''}` : 'Default (On)'}</option>
            <option value="true">On</option>
            <option value="false">Off</option>
          </select>
        </label>
      </>}
      {!showGeminiControls && <p className="sm:col-span-2 text-[10px] text-slate-500">Gemini-specific settings are hidden for this provider and retained if you switch back.</p>}
    </div>
  );
};

const API_KEY_LABELS = [
  { key: 'GEMINI_API_KEY', label: 'Gemini API key' },
  { key: 'GOOGLE_API_KEY', label: 'Google API key (Gemini alias)' },
  { key: 'OPENAI_API_KEY', label: 'OpenAI API key' },
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter API key' },
  { key: 'CUSTOM_API_KEY', label: 'Custom provider API key' },
];

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
  id?: string;
}

const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ checked, onChange, disabled, id }) => (
  <button
    id={id}
    type="button"
    role="switch"
    aria-checked={checked}
    disabled={disabled}
    onClick={() => !disabled && onChange(!checked)}
    className={`relative inline-flex h-4 w-8 shrink-0 cursor-pointer rounded-full transition-colors duration-150 ease-in-out focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed ${
      checked ? 'bg-[#f7f5f0]' : 'bg-[#383330] border border-[#3f3a36]'
    }`}
  >
    <span
      className={`pointer-events-none inline-block h-3 w-3 transform rounded-full transition duration-150 ease-in-out ${
        checked ? 'bg-[#2b2622] translate-x-4' : 'bg-[#aea69c] translate-x-0.5'
      }`}
    />
  </button>
);

export const SettingsView: React.FC<SettingsViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
  onProjectUpdated,
}) => {
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('general');
  const [categorySearch, setCategorySearch] = useState<string>('');
  const [machineEnvironment, setMachineEnvironment] = useState<MachineEnvironment | null>(null);
  const [loadingEnvironment, setLoadingEnvironment] = useState(true);
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({});
  const [clearApiKeys, setClearApiKeys] = useState<string[]>([]);
  const [savingEnvironment, setSavingEnvironment] = useState(false);
  const [modelCatalogs, setModelCatalogs] = useState<Partial<Record<ModelProvider, ModelCatalogResult>>>({});
  const [loadingModelCatalogs, setLoadingModelCatalogs] = useState<Partial<Record<ModelProvider, boolean>>>({});
  const [modelCatalogErrors, setModelCatalogErrors] = useState<Partial<Record<ModelProvider, string>>>({});
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResult | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [desktopUpdate, setDesktopUpdate] = useState<Update | null>(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [updateProgress, setUpdateProgress] = useState<number | null>(null);
  const [logsInfo, setLogsInfo] = useState<LogsInfoResult | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [openingLogsFolder, setOpeningLogsFolder] = useState(false);

  const loadLogsInfo = async () => {
    setLoadingLogs(true);
    try {
      const data = await fetchLogsInfo();
      setLogsInfo(data);
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleOpenLogsFolder = async () => {
    setOpeningLogsFolder(true);
    try {
      if (isTauriDesktop()) {
        try {
          await invoke('open_logs_directory');
          showToast('Opened logs folder in Explorer');
          return;
        } catch {
          // Fall back to HTTP endpoint
        }
      }
      const success = await openLogsDirectory();
      if (success) {
        showToast('Opened logs folder');
      } else {
        showToast('Could not open logs folder');
      }
    } finally {
      setOpeningLogsFolder(false);
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const loadSettingsData = async () => {
    if (!activeProjectPath) {
      setSettings(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const data = await fetchSettings(activeProjectPath);
    setSettings(data);
    setLoading(false);
  };

  const loadMachineEnvironment = async () => {
    setLoadingEnvironment(true);
    const data = await fetchMachineEnvironment();
    setMachineEnvironment(data);
    setLoadingEnvironment(false);
  };

  const loadModelCatalog = async (provider: ModelProvider) => {
    setLoadingModelCatalogs((current) => ({ ...current, [provider]: true }));
    setModelCatalogErrors((current) => ({ ...current, [provider]: '' }));
    try {
      const catalog = await fetchModelCatalog(provider);
      setModelCatalogs((current) => ({ ...current, [provider]: catalog }));
    } catch (error) {
      setModelCatalogErrors((current) => ({
        ...current,
        [provider]: getErrorMessage(error, `Could not load ${provider} model catalog.`),
      }));
    } finally {
      setLoadingModelCatalogs((current) => ({ ...current, [provider]: false }));
    }
  };

  useEffect(() => {
    loadSettingsData();
  }, [activeProjectPath]);

  useEffect(() => {
    loadMachineEnvironment();
  }, []);

  useEffect(() => {
    if (activeTab === 'logs' || activeTab === 'all') {
      void loadLogsInfo();
    }
  }, [activeTab]);


  const handleLoadEnvPresets = () => {
    if (!settings) return;
    const envPres = settings.env_presets || {};
    const envValues = machineEnvironment?.values || settings.env || {};
    setSettings({
      ...settings,
      model_name: envPres.model_name || envValues.NOVEL_MODEL || 'gemini-3.1-flash-lite',
      fallback_model: envPres.fallback_model || envValues.NOVEL_FALLBACK_MODEL || 'gemini-3.5-flash-lite',
      extractor_model: envPres.extractor_model || envValues.NOVEL_EXTRACTOR_MODEL || 'gemini-3.1-flash-lite',
      drafter_model: envPres.drafter_model || envValues.NOVEL_DRAFTER_MODEL || 'gemini-3.5-flash-lite',
      critic_model: envPres.critic_model || envValues.NOVEL_CRITIC_MODEL || 'gemma-4-26b-a4b-it',
      polisher_model: envPres.polisher_model || envValues.NOVEL_POLISHER_MODEL || 'gemini-3.5-flash-lite',
      chronicler_model: envPres.chronicler_model || envValues.NOVEL_CHRONICLER_MODEL || 'gemma-4-26b-a4b-it',
      scraper_model: envPres.scraper_model || envValues.NOVEL_SCRAPER_MODEL || '',
    });
    showToast('Loaded model presets from .env into form!');
  };

  const handleApplyPreset = (presetId: string) => {
    if (!settings || !presetId) return;
    const preset = settings.available_presets?.find((p) => p.id === presetId);
    if (!preset) return;
    setSettings({
      ...settings,
      model_name: preset.models.model_name ?? settings.model_name,
      fallback_model: preset.models.fallback_model ?? settings.fallback_model,
      extractor_model: preset.models.extractor_model ?? settings.extractor_model,
      drafter_model: preset.models.drafter_model ?? settings.drafter_model,
      critic_model: preset.models.critic_model ?? settings.critic_model,
      polisher_model: preset.models.polisher_model ?? settings.polisher_model,
      chronicler_model: preset.models.chronicler_model ?? settings.chronicler_model,
    });
    showToast(`Applied preset: ${preset.name}`);
  };

  const handleClearOverrides = () => {
    if (!settings) return;
    setSettings({
      ...settings,
      model_name: '',
      fallback_model: '',
      extractor_model: '',
      drafter_model: '',
      critic_model: '',
      polisher_model: '',
      chronicler_model: '',
      scraper_model: '',
      generation_settings: {},
    });
    showToast('Cleared all project model overrides (inheriting 100% from .env)');
  };

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeProjectPath || !settings) return;
    setSaving(true);
    // Exclude nested stale config and env snapshots before sending to backend
    const { config, env, machine_env, api_key_status, env_file_path, ...cleanSettings } = settings;
    const sanitizedSettings = {
      ...cleanSettings,
      // Review
      max_review_loops: Number(cleanSettings.max_review_loops) || 3,
      quality_threshold: Number(cleanSettings.quality_threshold) || 8.5,
      // Chunking
      chunk_threshold_lines:
        cleanSettings.chunk_threshold_lines === '' ||
        cleanSettings.chunk_threshold_lines === undefined ||
        isNaN(Number(cleanSettings.chunk_threshold_lines))
          ? 85
          : Number(cleanSettings.chunk_threshold_lines),
      chunk_size_lines:
        cleanSettings.chunk_size_lines === '' ||
        cleanSettings.chunk_size_lines === undefined ||
        isNaN(Number(cleanSettings.chunk_size_lines))
          ? 70
          : Number(cleanSettings.chunk_size_lines),
      chunk_overlap_lines:
        cleanSettings.chunk_overlap_lines === '' ||
        cleanSettings.chunk_overlap_lines === undefined ||
        isNaN(Number(cleanSettings.chunk_overlap_lines))
          ? 3
          : Number(cleanSettings.chunk_overlap_lines),
      // RAG
      rag_top_k: Number(cleanSettings.rag_top_k) || 2,
      rag_embedding_model: cleanSettings.rag_embedding_model?.trim() || '',
      rag_reranker_model: cleanSettings.rag_reranker_model?.trim() || '',
      // Safety
      safety_subdivision_min_lines:
        cleanSettings.safety_subdivision_min_lines === '' ||
        cleanSettings.safety_subdivision_min_lines === undefined ||
        isNaN(Number(cleanSettings.safety_subdivision_min_lines))
          ? 8
          : Number(cleanSettings.safety_subdivision_min_lines),
      safety_subdivision_max_depth:
        cleanSettings.safety_subdivision_max_depth === '' ||
        cleanSettings.safety_subdivision_max_depth === undefined ||
        isNaN(Number(cleanSettings.safety_subdivision_max_depth))
          ? 4
          : Number(cleanSettings.safety_subdivision_max_depth),
      // Rate Limits
      max_tpm:
        cleanSettings.max_tpm === '' ||
        cleanSettings.max_tpm === undefined ||
        isNaN(Number(cleanSettings.max_tpm))
          ? 32000
          : Number(cleanSettings.max_tpm),
      max_rpm:
        cleanSettings.max_rpm === '' ||
        cleanSettings.max_rpm === undefined ||
        isNaN(Number(cleanSettings.max_rpm))
          ? 60
          : Number(cleanSettings.max_rpm),
    };
    const success = await updateSettings(sanitizedSettings, activeProjectPath);
    setSaving(false);
    if (success) {
      showToast('Settings saved to config.yaml successfully!');
      await loadSettingsData();
      if (onProjectUpdated) {
        onProjectUpdated();
      }
    } else {
      alert('Failed to update project settings.');
    }
  };

  const handleSaveEnvironment = async () => {
    if (!machineEnvironment) return;
    setSavingEnvironment(true);
    const success = await saveMachineEnvironment({
      values: machineEnvironment.values,
      api_keys: apiKeyInputs,
      clear_api_keys: clearApiKeys,
    });
    setSavingEnvironment(false);
    if (success) {
      setApiKeyInputs({});
      setClearApiKeys([]);
      setModelCatalogs({});
      setModelCatalogErrors({});
      await loadMachineEnvironment();
      showToast('Local environment settings saved.');
    } else {
      alert('Could not save the local .env settings.');
    }
  };

  const handleCheckUpdates = async () => {
    setCheckingUpdates(true);
    setUpdateError(null);
    setUpdateInfo(null);
    try {
      if (desktopUpdate) {
        await desktopUpdate.close();
        setDesktopUpdate(null);
      }

      if (isTauriDesktop()) {
        try {
          const update = await check();
          if (update) {
            setDesktopUpdate(update);
            setUpdateInfo({
              current_version: update.currentVersion,
              latest_version: update.version,
              update_available: true,
              release_name: `NouSetsu ${update.version}`,
              release_notes: update.body || 'No release notes were provided.',
              release_url: 'https://github.com/Checkmartyr/NouSetsu/releases/latest',
              published_at: update.date,
              assets: [],
            });
            return;
          }
          if (isLocalUpdaterTest) {
            const currentVersion = await getVersion();
            setUpdateInfo({
              current_version: currentVersion,
              latest_version: currentVersion,
              update_available: false,
              release_name: 'Local updater test',
              release_notes: 'No update is available from the local feed.',
              release_url: '',
              assets: [],
            });
            return;
          }
        } catch (updaterError) {
          if (isLocalUpdaterTest) {
            setUpdateError(getErrorMessage(updaterError, 'Could not check the local update feed.'));
            return;
          }
          console.warn('Signed desktop update check failed; trying the release API.', updaterError);
        }
      }

      if (isLocalUpdaterTest) {
        setUpdateError('Local updater test mode requires the desktop app.');
        return;
      }

      setUpdateInfo(await checkLatestRelease());
    } catch (error) {
      setUpdateError(getErrorMessage(error, 'Could not check for updates.'));
    } finally {
      setCheckingUpdates(false);
    }
  };

  const handleInstallUpdate = async () => {
    if (!desktopUpdate) return;
    setInstallingUpdate(true);
    setUpdateError(null);
    setUpdateProgress(0);
    let contentLength: number | undefined;
    let downloadedBytes = 0;

    try {
      await desktopUpdate.download((event) => {
        if (event.event === 'Started') {
          contentLength = event.data.contentLength;
          setUpdateProgress(contentLength ? 0 : null);
        } else if (event.event === 'Progress') {
          downloadedBytes += event.data.chunkLength;
          if (contentLength && contentLength > 0) {
            setUpdateProgress(Math.min(100, Math.round((downloadedBytes / contentLength) * 100)));
          }
        } else if (event.event === 'Finished') {
          setUpdateProgress(100);
        }
      });
      await invoke('stop_backend_before_update');
      await desktopUpdate.install();
      await relaunch();
    } catch (error) {
      setUpdateError(getErrorMessage(error, 'Could not install the update.'));
      setInstallingUpdate(false);
      setUpdateProgress(null);
    }
  };

  const renderMachineEnvironmentSection = (groupId: string, group: GlobalEnvGroup) => {
    if (!machineEnvironment) return null;

    const roleConfig = groupId.startsWith('agent_')
      ? GENERATION_ROLES.find((item) => item.role === groupId.slice('agent_'.length))
      : undefined;
    const hiddenModelKeys = new Set(group.agent ? group.keys : groupId === 'models'
      ? ['DEFAULT_MODEL', 'NOVEL_MODEL', 'NOVEL_FALLBACK_MODEL', 'NOVEL_TEMPERATURE', 'NOVEL_THINKING_LEVEL', 'NOVEL_THINKING_BUDGET', 'NOVEL_USE_INTERACTIONS']
      : []);
    const visibleKeys = group.keys.filter((key) => !hiddenModelKeys.has(key));
    const selectedModelRoute = roleConfig
      ? machineEnvironment.values[`NOVEL_${roleConfig.role.toUpperCase()}_MODEL`]
        || machineEnvironment.values.NOVEL_MODEL
        || machineEnvironment.values.DEFAULT_MODEL
        || ''
      : '';
    const updateEnvironmentValue = (key: string, value: string) => setMachineEnvironment((current) => current ? {
      ...current,
      values: { ...current.values, [key]: value },
    } : current);

    return (
      <section
        key={groupId}
        className={`bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4 ${group.agent ? 'h-full' : ''}`}
      >
        <div className="flex items-center gap-2 border-b border-[#4a433e] pb-3">
          {group.agent ? <Bot className="w-4 h-4 shrink-0 text-purple-300" /> : <KeyRound className="w-4 h-4 shrink-0 text-amber-300" />}
          <div>
            <h2 className="text-sm font-bold text-slate-200">{group.title}</h2>
            <p className="text-[11px] text-slate-400 mt-1">
              {group.description || 'Machine defaults saved in the local .env file.'}
            </p>
          </div>
        </div>

        {visibleKeys.length > 0 && <div className={`grid grid-cols-1 ${group.agent ? 'sm:grid-cols-2 xl:grid-cols-3' : 'sm:grid-cols-2'} gap-3 text-xs`}>
          {visibleKeys.map((key) => {
            const suffix = key.replace(/^NOVEL_[A-Z]+_/, '');
            const label = group.agent ? AGENT_ENV_LABELS[suffix] || key : GLOBAL_ENV_LABELS[key] || key;
            return (
              <label key={key} className="block min-w-0">
                <span className={`block text-slate-400 mb-1 ${group.agent ? 'font-medium' : 'font-mono'}`}>{label}</span>
                <input
                  type="text"
                  value={machineEnvironment.values[key] || ''}
                  onChange={(event) => updateEnvironmentValue(key, event.target.value)}
                  aria-label={`${group.title} ${label}`}
                  className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </label>
            );
          })}
        </div>}

        {groupId === 'models' && (
          <div className="space-y-4 border-b border-[#4a433e] pb-4">
            <h3 className="text-xs font-semibold text-slate-200">Global model routes</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { key: 'DEFAULT_MODEL', label: 'Default model' },
                { key: 'NOVEL_MODEL', label: 'Primary model' },
                { key: 'NOVEL_FALLBACK_MODEL', label: 'Shared fallback model' },
              ].map(({ key, label }) => (
                <ModelRouteControl
                  key={key}
                  label={label}
                  value={machineEnvironment.values[key] || ''}
                  onChange={(value) => updateEnvironmentValue(key, value)}
                  catalogs={modelCatalogs}
                  loadingCatalogs={loadingModelCatalogs}
                  catalogErrors={modelCatalogErrors}
                  apiKeyStatus={machineEnvironment.api_key_status}
                  customBaseUrl={machineEnvironment.values.CUSTOM_API_BASE_URL}
                  onLoadCatalog={loadModelCatalog}
                />
              ))}
            </div>
            <div className="rounded border border-[#4a433e] p-3 space-y-2">
              <h3 className="text-xs font-semibold text-slate-200">Shared generation defaults</h3>
              <p className="text-[10px] text-slate-400">Role-specific values below override these defaults. A shared fallback uses the invoking agent’s generation controls.</p>
              <GenerationSettingsEditor
                role="default"
                provider="all"
                environmentValues={machineEnvironment.values}
                onEnvironmentChange={updateEnvironmentValue}
              />
            </div>
          </div>
        )}

        {roleConfig && (
          <div className="space-y-3">
            <ModelRouteControl
              label="Model route"
              value={machineEnvironment.values[`NOVEL_${roleConfig.role.toUpperCase()}_MODEL`] || ''}
              onChange={(value) => updateEnvironmentValue(`NOVEL_${roleConfig.role.toUpperCase()}_MODEL`, value)}
              catalogs={modelCatalogs}
              loadingCatalogs={loadingModelCatalogs}
              catalogErrors={modelCatalogErrors}
              apiKeyStatus={machineEnvironment.api_key_status}
              customBaseUrl={machineEnvironment.values.CUSTOM_API_BASE_URL}
              onLoadCatalog={loadModelCatalog}
            />
            <GenerationSettingsEditor
              role={roleConfig.role}
              provider={providerForRoute(selectedModelRoute)}
              model={modelIdForRoute(selectedModelRoute)}
              environmentValues={machineEnvironment.values}
              onEnvironmentChange={updateEnvironmentValue}
            />
          </div>
        )}

        {groupId === 'models' && (
          <div className="border-t border-[#4a433e] pt-4 space-y-3">
            <div>
              <h3 className="text-xs font-semibold text-slate-200">Provider API keys</h3>
              <p className="text-[10px] text-slate-400 mt-1">Keys are stored locally and never returned to the browser. Leave blank to keep a saved key; status reflects this .env file.</p>

            </div>
            <label className="block text-xs">
              <span className="block font-medium text-slate-300 mb-1">Custom OpenAI-compatible base URL</span>
              <input
                type="url"
                value={machineEnvironment.values.CUSTOM_API_BASE_URL || ''}
                onChange={(event) => updateEnvironmentValue('CUSTOM_API_BASE_URL', event.target.value)}
                placeholder="https://provider.example/v1"
                aria-label="Custom OpenAI-compatible base URL"
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
              />
              <span className="block text-[10px] text-slate-500 mt-1">Model discovery uses the OpenAI-compatible /models endpoint; model IDs can also be entered manually.</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              {API_KEY_LABELS.map(({ key, label }) => {
                const configured = Boolean(machineEnvironment.api_key_status[key]);
                const markedForRemoval = clearApiKeys.includes(key);
                return (
                  <div key={key} className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <label htmlFor={`api-key-${key}`} className="font-medium text-slate-300">{label}</label>
                      <span className={configured && !markedForRemoval ? 'text-emerald-400 text-[10px]' : 'text-slate-500 text-[10px]'}>
                        {markedForRemoval ? 'Will be removed' : configured ? 'Configured' : 'Not configured'}
                      </span>
                    </div>
                    <input
                      id={`api-key-${key}`}
                      type="password"
                      autoComplete="new-password"
                      value={apiKeyInputs[key] || ''}
                      onChange={(event) => {
                        setApiKeyInputs((current) => ({ ...current, [key]: event.target.value }));
                        setClearApiKeys((current) => current.filter((item) => item !== key));
                      }}
                      placeholder={configured ? 'Enter a new key to replace the saved one' : 'Paste API key'}
                      className="w-full bg-[#2b2622] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    />
                    {configured && (
                      <button
                        type="button"
                        onClick={() => {
                          setClearApiKeys((current) => markedForRemoval ? current.filter((item) => item !== key) : [...current, key]);
                          setApiKeyInputs((current) => ({ ...current, [key]: '' }));
                        }}
                        className="text-[10px] text-rose-300 hover:text-rose-200"
                      >
                        {markedForRemoval ? 'Undo clear' : 'Clear saved key'}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[10px] text-slate-500">Save .env to persist the machine defaults and any API key changes.</p>
          </div>
        )}

        {groupId === 'paths' && (
          <p className="text-[10px] text-slate-500">On desktop, project/ is created beside the app when writable; otherwise projects use app data. An explicit NOVEL_PROJECTS_DIR takes precedence.</p>
        )}


      </section>
    );
  };

  // Keyboard shortcut: Ctrl+S or Cmd+S saves the visible settings section.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (activeTab === 'updates' || activeTab === 'logs') return;
        if (activeTab === 'global') {
          handleSaveEnvironment();
          return;
        }
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab, settings, activeProjectPath, machineEnvironment, apiKeyInputs, clearApiKeys]);

  const filteredCategories = SETTING_CATEGORIES.filter((cat) => {
    if (!categorySearch.trim()) return true;
    const q = categorySearch.toLowerCase();
    return cat.name.toLowerCase().includes(q) || cat.shortDesc.toLowerCase().includes(q);
  });

  const showAll = activeTab === 'all';

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#2b2622] text-[#f7f5f0]">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-16 right-8 z-50 px-3.5 py-1.5 bg-[#383330] text-[#f7f5f0] border border-[#3f3a36] rounded-[4px] shadow-lg text-xs font-medium flex items-center gap-2 animate-fade-in">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="bg-[#2b2622] border-b border-[#3f3a36] px-6 py-3 flex items-center justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-[#dad2c1]" />
            <h1 className="text-base font-medium tracking-[-0.3px] text-[#f7f5f0]">
              {activeTab === 'global'
                ? 'Global Settings'
                : activeTab === 'updates'
                  ? 'App Updates'
                  : activeTab === 'logs'
                    ? 'Logs & Diagnostics'
                    : `Project Settings: ${settings?.title || activeProjectTitle || 'No project selected'}`}
            </h1>
          </div>
          <p className="text-xs text-[#aea69c] mt-0.5">
            {activeTab === 'global'
              ? 'Machine-wide defaults and provider credentials shared across projects.'
              : activeTab === 'updates'
                ? 'Check for NouSetsu desktop releases.'
                : activeTab === 'logs'
                  ? 'View local persistent log files for debugging and diagnostics.'
                  : <>Project-specific options are saved in <code className="text-[#dad2c1] font-mono">.novel/config.yaml</code>.</>}
          </p>
        </div>

        {!['global', 'updates', 'logs'].includes(activeTab) && (
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-block text-[11px] text-[#aea69c] font-mono">
              Press <kbd className="px-1.5 py-0.5 bg-[#383330] border border-[#3f3a36] rounded-[2px] text-[#dad2c1]">Ctrl+S</kbd> to save
            </span>
            <button
              onClick={() => handleSave()}
              disabled={saving || !settings}
              className="btn-primary text-xs flex items-center gap-1.5"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save Settings'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Main 2-Column Layout */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Left Sidebar: Settings Groups */}
        <aside className="w-full md:w-64 bg-[#2b2622] border-b md:border-b-0 md:border-r border-[#3f3a36] flex flex-col shrink-0 max-h-48 md:max-h-none overflow-hidden">
          {/* Quick Search */}
          <div className="p-3 border-b border-[#3f3a36]">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#aea69c] absolute left-2.5 top-2" />
              <input
                type="text"
                value={categorySearch}
                onChange={(e) => setCategorySearch(e.target.value)}
                placeholder="Search settings..."
                className="input-text w-full pl-8 pr-2.5 py-1 text-xs"
              />
              {categorySearch && (
                <button
                  onClick={() => setCategorySearch('')}
                  className="absolute right-2.5 top-2 text-[#aea69c] hover:text-[#f7f5f0]"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Navigation Category List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-3">
            {(['global', 'project'] as const).map((group) => {
              const groupCategories = filteredCategories.filter((category) => category.group === group);
              if (!groupCategories.length) return null;
              return (
                <div key={group} className="space-y-0.5">
                  <div className="px-2.5 pt-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[#8e8579]">
                    {group === 'global' ? 'Global Settings' : 'Project Settings'}
                  </div>
                  {groupCategories.map((cat) => {
                    const Icon = cat.icon;
                    const isActive = activeTab === cat.id;
                    return (
                      <button
                        key={cat.id}
                        onClick={() => setActiveTab(cat.id)}
                        className={`w-full text-left px-2.5 py-1.5 rounded-[3px] transition-colors flex items-center gap-2 group cursor-pointer ${
                          isActive
                            ? 'bg-[#383330] text-[#f7f5f0] border-l-2 border-[#f7f5f0] font-medium'
                            : 'hover:bg-[#383330]/50 text-[#c9c0ad] hover:text-[#f7f5f0] border-l-2 border-transparent'
                        }`}
                      >
                        <Icon
                          className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                            isActive ? 'text-[#f7f5f0]' : 'text-[#aea69c] group-hover:text-[#dad2c1]'
                          }`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs truncate">{cat.name}</div>
                          <div className="text-[10px] text-[#aea69c] truncate">{cat.shortDesc}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Sidebar Footer info */}
          <div className="p-3 border-t border-[#3f3a36] bg-[#2b2622] text-[11px] text-[#aea69c] hidden md:flex items-center justify-between">
            <span>Project ID:</span>
            <span className="font-mono text-[#dad2c1] truncate max-w-[120px]">
              {settings?.project_id || 'default_project'}
            </span>
          </div>
        </aside>

        {/* Right Content Area: Form Panes */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 flex justify-center bg-[#2b2622] min-w-0">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-[#aea69c] text-xs gap-3">
              <RefreshCw className="w-5 h-5 animate-spin text-[#dad2c1]" />
              <span>Loading project settings...</span>
            </div>
          ) : !settings && !['global', 'updates'].includes(activeTab) ? (
            <div className="flex flex-col items-center justify-center py-20 text-[#aea69c] text-xs gap-3">
              <Settings className="w-8 h-8 text-[#aea69c]" />
              <p>No project selected or config.yaml not found.</p>
              <p className="text-[11px] text-[#8e8579]">Select a project for project settings. Machine environment values are available in their related settings tabs.</p>
            </div>
          ) : (
            <div className="max-w-4xl w-full space-y-6 pb-16">
              {settings && activeTab !== 'global' && <form onSubmit={handleSave} className="space-y-6">
              {/* Group 1: General Novel Information */}
              {(showAll || activeTab === 'general') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2">
                      <Sliders className="w-4 h-4 text-indigo-400" />
                      <h2 className="text-sm font-bold text-slate-200">Novel Information & Metadata</h2>
                    </div>
                    {settings.created_at && (
                      <span className="text-[10px] text-slate-500 font-mono">
                        Created: {new Date(settings.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Novel Title</label>
                      <input
                        type="text"
                        value={settings.title || ''}
                        onChange={(e) => setSettings({ ...settings, title: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="Ascendance of a Bookworm"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Genre</label>
                      <input
                        type="text"
                        value={settings.genre || ''}
                        onChange={(e) => setSettings({ ...settings, genre: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="isekai, xianxia, litrpg, romance..."
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Source Language</label>
                      <input
                        type="text"
                        value={settings.source_language || ''}
                        onChange={(e) => setSettings({ ...settings, source_language: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="Japanese, Chinese, Korean, English..."
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Target Language</label>
                      <input
                        type="text"
                        value={settings.target_language || ''}
                        onChange={(e) => setSettings({ ...settings, target_language: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="English, Thai, French, Spanish..."
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-slate-400 mb-1 font-medium">Project Identifier</label>
                      <input
                        type="text"
                        value={settings.project_id || ''}
                        onChange={(e) => setSettings({ ...settings, project_id: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-400 font-mono text-xs focus:outline-none focus:border-indigo-500"
                        placeholder="default_project"
                      />
                      <p className="text-[10px] text-slate-500 mt-1">
                        Unique machine identifier for caching and multi-project registry indexing.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 2: Multi-Agent Model Routing & Presets */}
              {(showAll || activeTab === 'models') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-5 h-5 text-purple-400" />
                      <div>
                        <h2 className="text-sm font-bold text-slate-200">
                          Multi-Agent Model Routing & Fallback Cascade
                        </h2>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Assign specialized LLMs per stage, configure global failover, and apply presets.
                        </p>
                      </div>
                    </div>

                    {/* Presets Toolbar */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <select
                        onChange={(e) => {
                          handleApplyPreset(e.target.value);
                          e.target.value = '';
                        }}
                        defaultValue=""
                        className="bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
                      >
                        <option value="" disabled>
                          ⚡ Apply Model Preset...
                        </option>
                        {settings.available_presets?.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>

                      <button
                        type="button"
                        onClick={handleLoadEnvPresets}
                        title="Load model defaults directly from machine .env"
                        className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium cursor-pointer border border-slate-700"
                      >
                        <Download className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Load .env</span>
                      </button>

                      <button
                        type="button"
                        onClick={handleClearOverrides}
                        title="Clear all project overrides to inherit 100% from .env"
                        className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 rounded-lg text-xs font-medium cursor-pointer border border-slate-700/60"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
                        <span>Clear</span>
                      </button>
                    </div>
                  </div>

                  {/* Primary & Global Fallback */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="font-semibold text-slate-200 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Primary Default Model Override
                        </label>
                        {settings.model_name && (
                          <button
                            type="button"
                            onClick={() => setSettings({ ...settings, model_name: '' })}
                            className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                          >
                            <X className="w-3 h-3" /> Clear
                          </button>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400">
                        Default model across stages unless explicitly overridden below or in .env.
                      </p>
                      <ModelRouteControl
                        label="Primary model route"
                        value={settings.model_name || ''}
                        effectiveValue={settings.effective_model_name || settings.env_presets?.model_name}
                        onChange={(value) => setSettings({ ...settings, model_name: value })}
                        catalogs={modelCatalogs}
                        loadingCatalogs={loadingModelCatalogs}
                        catalogErrors={modelCatalogErrors}
                        apiKeyStatus={machineEnvironment?.api_key_status}
                        customBaseUrl={machineEnvironment?.values.CUSTOM_API_BASE_URL}
                        onLoadCatalog={loadModelCatalog}
                        inherit
                      />
                      <div className="text-[10px] text-slate-500 flex justify-between">
                        <span>
                          Active:{' '}
                          <strong className="text-slate-400 font-mono">
                            {settings.model_name || settings.effective_model_name || 'gemini-3.1-flash-lite'}
                          </strong>
                        </span>
                        {settings.model_name ? (
                          <span className="text-purple-400 font-medium">Project Override</span>
                        ) : (
                          <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                        )}
                      </div>
                    </div>

                    <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="font-semibold text-slate-200 flex items-center gap-1.5">
                          <Bot className="w-3.5 h-3.5 text-purple-400" /> Global Fallback Model Override
                        </label>
                        {settings.fallback_model && (
                          <button
                            type="button"
                            onClick={() => setSettings({ ...settings, fallback_model: '' })}
                            className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                          >
                            <X className="w-3 h-3" /> Clear
                          </button>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400">
                        Shared failover route for all stages; it inherits the invoking agent’s generation controls.
                      </p>
                      <ModelRouteControl
                        label="Shared fallback route"
                        value={settings.fallback_model || ''}
                        effectiveValue={settings.effective_fallback_model || settings.env_presets?.fallback_model}
                        onChange={(value) => setSettings({ ...settings, fallback_model: value })}
                        catalogs={modelCatalogs}
                        loadingCatalogs={loadingModelCatalogs}
                        catalogErrors={modelCatalogErrors}
                        apiKeyStatus={machineEnvironment?.api_key_status}
                        customBaseUrl={machineEnvironment?.values.CUSTOM_API_BASE_URL}
                        onLoadCatalog={loadModelCatalog}
                        inherit
                      />
                      <div className="text-[10px] text-slate-500 flex justify-between">
                        <span>
                          Active:{' '}
                          <strong className="text-slate-400 font-mono">
                            {settings.fallback_model || settings.effective_fallback_model || 'gemini-3.5-flash-lite'}
                          </strong>
                        </span>
                        {settings.fallback_model ? (
                          <span className="text-purple-400 font-medium">Project Override</span>
                        ) : (
                          <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3 pt-2">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Pipeline and scraper routes</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {GENERATION_ROLES.map((roleConfig) => {
                        const route = String(settings[roleConfig.modelKey] || '');
                        const effectiveRoute = String(settings[roleConfig.effectiveModelKey] || '');
                        const selectedRoute = route || effectiveRoute;
                        const provider = providerForRoute(selectedRoute);
                        return (
                          <div key={roleConfig.role} className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-3">
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="px-1.5 py-0.5 bg-indigo-500/10 text-indigo-300 rounded text-[10px] font-semibold">{roleConfig.stage}</span>
                                <span className="font-semibold text-slate-200">{roleConfig.title}</span>
                              </div>
                              <p className="text-[10px] text-slate-400 mt-1">{roleConfig.description}</p>
                            </div>
                            <ModelRouteControl
                              label={`${roleConfig.title} model`}
                              value={route}
                              effectiveValue={effectiveRoute || undefined}
                              onChange={(value) => setSettings({ ...settings, [roleConfig.modelKey]: value })}
                              catalogs={modelCatalogs}
                              loadingCatalogs={loadingModelCatalogs}
                              catalogErrors={modelCatalogErrors}
                              apiKeyStatus={machineEnvironment?.api_key_status}
                              customBaseUrl={machineEnvironment?.values.CUSTOM_API_BASE_URL}
                              onLoadCatalog={loadModelCatalog}
                              inherit
                            />
                            <GenerationSettingsEditor
                              role={roleConfig.role}
                              provider={provider}
                              model={modelIdForRoute(selectedRoute)}
                              projectValue={settings.generation_settings?.[roleConfig.role]}
                              effectiveValue={settings.effective_generation_settings?.[roleConfig.role]}
                              onProjectChange={(value) => setSettings({
                                ...settings,
                                generation_settings: {
                                  ...settings.generation_settings,
                                  [roleConfig.role]: value,
                                },
                              })}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>

                </div>
              )}

              {/* Group 3: Reflection Review & Quality Controls */}
              {(showAll || activeTab === 'review') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-5">
                  <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                    <RefreshCw className="w-4 h-4 text-amber-400" />
                    <h2 className="text-sm font-bold text-slate-200">
                      LangGraph Reflection Review Cycle & Quality Control
                    </h2>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Max Review Loops ({settings.max_review_loops ?? 3})
                      </label>
                      <input
                        type="range"
                        min={1}
                        max={5}
                        value={settings.max_review_loops ?? 3}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            max_review_loops: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full accent-indigo-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                        <span>1 (Fast)</span>
                        <span>2 (Balanced)</span>
                        <span>3 (Standard)</span>
                        <span>5 (Exhaustive)</span>
                      </div>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Quality Score Threshold ({settings.quality_threshold ?? 8.5})
                      </label>
                      <input
                        type="range"
                        min={6.0}
                        max={9.5}
                        step={0.1}
                        value={settings.quality_threshold ?? 8.5}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            quality_threshold: parseFloat(e.target.value),
                          })
                        }
                        className="w-full accent-indigo-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                        <span>6.0 (Permissive)</span>
                        <span>8.5 (Default target)</span>
                        <span>9.5 (Perfectionist)</span>
                      </div>
                    </div>
                  </div>

                  {/* Patch Polishing Diff Engine */}
                  <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 text-xs">
                    <div>
                      <div className="font-semibold text-slate-200">Enable Diff/Patch Polishing Engine</div>
                      <div className="text-[11px] text-slate-400">
                        Generates targeted search/replace diff patches in reflection review loops rather than rewriting full chapters, slashing polisher token consumption.
                      </div>
                    </div>
                    <ToggleSwitch
                      checked={settings.enable_patch_polishing !== false}
                      onChange={(val) => setSettings({ ...settings, enable_patch_polishing: val })}
                    />
                  </div>
                </div>
              )}

              {/* Group 4: Semantic Chunking Parameters */}
              {(showAll || activeTab === 'chunking') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2">
                      <Layers className="w-4 h-4 text-pink-400" />
                      <h2 className="text-sm font-bold text-slate-200">
                        Line-Based Semantic Chunking
                      </h2>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400 text-[11px]">Chunking Enabled</span>
                      <ToggleSwitch
                        checked={settings.enable_chunking !== false}
                        onChange={(val) => setSettings({ ...settings, enable_chunking: val })}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-slate-400">
                    Chapters exceeding the threshold are automatically partitioned into semantic chunks with running overlap context to prevent token overflow.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Chunk Threshold (lines)
                      </label>
                      <input
                        type="number"
                        min={1}
                        placeholder="800"
                        value={settings.chunk_threshold_lines === '' ? '' : (settings.chunk_threshold_lines ?? 800)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            chunk_threshold_lines: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.chunk_threshold_lines === '' ||
                            settings.chunk_threshold_lines === undefined ||
                            isNaN(Number(settings.chunk_threshold_lines))
                          ) {
                            setSettings({ ...settings, chunk_threshold_lines: 800 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Minimum non-empty lines to trigger chunking</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Chunk Size (lines)</label>
                      <input
                        type="number"
                        min={1}
                        placeholder="400"
                        value={settings.chunk_size_lines === '' ? '' : (settings.chunk_size_lines ?? 400)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            chunk_size_lines: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.chunk_size_lines === '' ||
                            settings.chunk_size_lines === undefined ||
                            isNaN(Number(settings.chunk_size_lines))
                          ) {
                            setSettings({ ...settings, chunk_size_lines: 400 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Target line count per chunk</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Chunk Overlap (lines)
                      </label>
                      <input
                        type="number"
                        min={0}
                        placeholder="3"
                        value={settings.chunk_overlap_lines === '' ? '' : (settings.chunk_overlap_lines ?? 3)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            chunk_overlap_lines: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.chunk_overlap_lines === '' ||
                            settings.chunk_overlap_lines === undefined ||
                            isNaN(Number(settings.chunk_overlap_lines))
                          ) {
                            setSettings({ ...settings, chunk_overlap_lines: 3 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Preceding context lines passed forward</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 5: Narrative Memory & Novel Bible */}
              {(showAll || activeTab === 'memory') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                    <BookMarked className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm font-bold text-slate-200">
                      Narrative Memory, Bible & Filtering
                    </h2>
                  </div>

                  <div className="space-y-3 text-xs">
                    {/* Auto-update Bible */}
                    <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Auto-Update Novel Bible</div>
                        <div className="text-[11px] text-slate-400">
                          Automatically merge newly discovered terms, character records, and chapter summaries into <code className="text-slate-300 font-mono">bible.yaml</code>.
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.auto_update_bible !== false}
                        onChange={(val) => setSettings({ ...settings, auto_update_bible: val })}
                      />
                    </div>

                    {/* Cross-folder summaries */}
                    <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Cross-Folder Multi-Volume Memory</div>
                        <div className="text-[11px] text-slate-400">
                          Backfill narrative summaries from preceding volumes when translating sequential volume folders (e.g. Vol_01 to Vol_02).
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.cross_folder_summaries !== false}
                        onChange={(val) => setSettings({ ...settings, cross_folder_summaries: val })}
                      />
                    </div>

                    {/* Filter scene characters */}
                    <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Scene Character Filtering</div>
                        <div className="text-[11px] text-slate-400">
                          Filter character roster per scene chunk based on textual presence and core roles to avoid LLM context noise.
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.filter_scene_characters !== false}
                        onChange={(val) => setSettings({ ...settings, filter_scene_characters: val })}
                      />
                    </div>

                    {/* Filter extractor entities */}
                    <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Extractor Known Entity Filtering</div>
                        <div className="text-[11px] text-slate-400">
                          Filter known characters and glossary items before entity extraction to reduce token usage and avoid quota exhaustion.
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.filter_extractor_entities !== false}
                        onChange={(val) => setSettings({ ...settings, filter_extractor_entities: val })}
                      />
                    </div>

                    {/* Post-polish term reconciliation */}
                    <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Post-Polish Term Reconciliation</div>
                        <div className="text-[11px] text-slate-400">
                          Chronicler Agent reconciles provisional pre-translation terms against final polished publication prose.
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.enable_post_polish_reconciliation !== false}
                        onChange={(val) => setSettings({ ...settings, enable_post_polish_reconciliation: val })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Group 6: Episodic Lore & Hybrid RAG (Tier 4) */}
              {(showAll || activeTab === 'rag') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" />
                      <h2 className="text-sm font-bold text-slate-200">
                        Episodic Lore & Hybrid RAG (Tier 4 Memory)
                      </h2>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400 text-[11px]">Hybrid RAG Enabled</span>
                      <ToggleSwitch
                        checked={settings.enable_rag !== false}
                        onChange={(val) => setSettings({ ...settings, enable_rag: val })}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-slate-400">
                    Local SQLite <code className="text-slate-300 font-mono">lore.db</code> FTS5 lexical BM25 + Gemini vector embedding store for long-range cross-chapter continuity.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Lore Retrieval Top-K ({settings.rag_top_k ?? 2})
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        placeholder="2"
                        value={settings.rag_top_k ?? 2}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            rag_top_k: parseInt(e.target.value, 10) || 2,
                          })
                        }
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Historical lore snippets retrieved per chapter (1–10)</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Dense Embedding Model</label>
                      <input
                        type="text"
                        value={settings.rag_embedding_model || ''}
                        onChange={(e) => setSettings({ ...settings, rag_embedding_model: e.target.value })}
                        placeholder="text-multilingual-embedding-002"
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Leave blank for default (text-multilingual-embedding-002)</span>
                    </div>

                    <div className="sm:col-span-2 flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3">
                      <div>
                        <div className="font-semibold text-slate-200">Enable Cross-Encoder Reranker</div>
                        <div className="text-[11px] text-slate-400">
                          Applies a second-stage joint LLM cross-encoder over hybrid candidates for superior retrieval relevance.
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={settings.enable_rag_reranker !== false}
                        onChange={(val) => setSettings({ ...settings, enable_rag_reranker: val })}
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-slate-400 mb-1 font-medium">Cross-Encoder Reranker Model</label>
                      <input
                        type="text"
                        list="model-suggestions"
                        value={settings.rag_reranker_model || ''}
                        onChange={(e) => setSettings({ ...settings, rag_reranker_model: e.target.value })}
                        placeholder="gemini-3.5-flash-lite"
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Leave blank for default (gemini-3.5-flash-lite)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 7: AI Safety & Bisection Engine */}
              {(showAll || activeTab === 'safety') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-orange-400" />
                      <h2 className="text-sm font-bold text-slate-200">
                        AI Safety Block Resilience & Bisection Engine
                      </h2>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400 text-[11px]">Subdivision Enabled</span>
                      <ToggleSwitch
                        checked={settings.safety_recursive_subdivision !== false}
                        onChange={(val) => setSettings({ ...settings, safety_recursive_subdivision: val })}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-slate-400">
                    Catches commercial AI safety blocks (<code className="text-slate-300 font-mono">prohibited_content</code> HTTP 400) on combat or romance and recursively bisects chunks down to minimal sensitive snippets.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Subdivision Min Lines (lines)
                      </label>
                      <input
                        type="number"
                        min={2}
                        placeholder="8"
                        value={settings.safety_subdivision_min_lines === '' ? '' : (settings.safety_subdivision_min_lines ?? 8)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            safety_subdivision_min_lines: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.safety_subdivision_min_lines === '' ||
                            settings.safety_subdivision_min_lines === undefined ||
                            isNaN(Number(settings.safety_subdivision_min_lines))
                          ) {
                            setSettings({ ...settings, safety_subdivision_min_lines: 8 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Minimum line threshold before falling back to Google Translate bypass</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Subdivision Max Recursion Depth
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        placeholder="4"
                        value={settings.safety_subdivision_max_depth === '' ? '' : (settings.safety_subdivision_max_depth ?? 4)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            safety_subdivision_max_depth: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.safety_subdivision_max_depth === '' ||
                            settings.safety_subdivision_max_depth === undefined ||
                            isNaN(Number(settings.safety_subdivision_max_depth))
                          ) {
                            setSettings({ ...settings, safety_subdivision_max_depth: 4 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Maximum bisection recursion tree depth (default: 4)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 8: Rate Limiting & Quota Guard */}
              {(showAll || activeTab === 'ratelimit') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                    <Zap className="w-4 h-4 text-yellow-400" />
                    <h2 className="text-sm font-bold text-slate-200">
                      Rate Limiting & Provider Quota Guard
                    </h2>
                  </div>

                  <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 text-xs text-slate-400 flex items-start gap-2.5">
                    <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                    <div>
                      Sliding window rate limiter monitors 60-second usage windows, calculating precise backoff sleep intervals until windows clear to prevent HTTP 429 quota exhaustion.
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Max Tokens Per Minute (TPM)
                      </label>
                      <input
                        type="number"
                        min={1000}
                        placeholder="32000"
                        value={settings.max_tpm === '' ? '' : (settings.max_tpm ?? 32000)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            max_tpm: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.max_tpm === '' ||
                            settings.max_tpm === undefined ||
                            isNaN(Number(settings.max_tpm))
                          ) {
                            setSettings({ ...settings, max_tpm: 32000 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">60-second sliding window TPM limit (default: 32,000)</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">
                        Max Requests Per Minute (RPM)
                      </label>
                      <input
                        type="number"
                        min={1}
                        placeholder="60"
                        value={settings.max_rpm === '' ? '' : (settings.max_rpm ?? 60)}
                        onChange={(e) => {
                          const val = e.target.value;
                          setSettings({
                            ...settings,
                            max_rpm: val === '' || isNaN(parseInt(val, 10)) ? '' : parseInt(val, 10),
                          });
                        }}
                        onBlur={() => {
                          if (
                            settings.max_rpm === '' ||
                            settings.max_rpm === undefined ||
                            isNaN(Number(settings.max_rpm))
                          ) {
                            setSettings({ ...settings, max_rpm: 60 });
                          }
                        }}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">60-second sliding window RPM limit (default: 60)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 9: Directory Paths */}
              {(showAll || activeTab === 'paths') && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                    <Folder className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm font-bold text-slate-200">Workspace Directory Paths</h2>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                    <div>
                      <label className="block text-slate-400 mb-1 font-sans font-medium">
                        Raw Chapters Directory
                      </label>
                      <input
                        type="text"
                        value={settings.raw_dir || ''}
                        onChange={(e) => setSettings({ ...settings, raw_dir: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="raw_chapters"
                      />
                      <span className="text-[10px] text-slate-500 font-sans">Folder where raw novel text files are stored</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-sans font-medium">
                        Translated Chapters Directory
                      </label>
                      <input
                        type="text"
                        value={settings.translated_dir || settings.output_dir || ''}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            translated_dir: e.target.value,
                            output_dir: e.target.value,
                          })
                        }
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="translated_chapters"
                      />
                      <span className="text-[10px] text-slate-500 font-sans">Folder where finished markdown translations are exported</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Shared Model Datalist for autocomplete */}
              <datalist id="model-suggestions">
                {settings.model_catalog?.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>

              {/* Bottom Save Button row */}
              {!['global', 'updates'].includes(activeTab) && (
                <div className="pt-4 flex justify-end">
                  <button
                    type="submit"
                    disabled={saving || !settings}
                    className="flex items-center gap-1.5 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    {saving ? 'Saving...' : 'Save Settings to config.yaml'}
                  </button>
                </div>
              )}
            </form>}

              {activeTab === 'global' && (
                <>
                  {machineEnvironment ? (
                    <>
                      <section className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-2">
                        <div className="flex items-center gap-2">
                          <KeyRound className="w-4 h-4 text-amber-300" />
                          <h2 className="text-sm font-bold text-slate-200">Machine-wide Environment</h2>
                        </div>
                        <p className="text-xs text-slate-400">These defaults apply across projects unless a project setting overrides them.</p>
                        <p className="text-[10px] text-slate-500 font-mono break-all">.env: {machineEnvironment.env_file_path}</p>
                      </section>
                      {GLOBAL_ENV_ENTRIES.slice(0, FIRST_AGENT_ENV_GROUP_INDEX).map(([groupId, group]) =>
                        renderMachineEnvironmentSection(groupId, group)
                      )}
                      {AGENT_ENV_GROUPS.length > 0 && (
                        <section className="space-y-3">
                          <div className="flex items-center gap-2 px-1">
                            <Bot className="w-4 h-4 text-purple-300" />
                            <div>
                              <h2 className="text-sm font-bold text-slate-200">Pipeline Agent Defaults</h2>
                              <p className="text-[11px] text-slate-400 mt-0.5">Configure each stage independently; project Model Routing overrides these machine-wide defaults.</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                            {AGENT_ENV_GROUPS.map(([groupId, group]) =>
                              renderMachineEnvironmentSection(groupId, group)
                            )}
                          </div>
                        </section>
                      )}
                      {GLOBAL_ENV_ENTRIES.slice(FIRST_AGENT_ENV_GROUP_INDEX)
                        .filter(([, group]) => !group.agent)
                        .map(([groupId, group]) => renderMachineEnvironmentSection(groupId, group))}
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={handleSaveEnvironment}
                          disabled={savingEnvironment}
                          className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <Save className="w-3.5 h-3.5" />
                          {savingEnvironment ? 'Saving .env...' : 'Save Global Settings'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <section className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4 text-xs text-slate-400 flex items-center justify-between">
                      <span>{loadingEnvironment ? 'Loading global environment settings...' : 'Could not load global environment settings.'}</span>
                      {!loadingEnvironment && <button type="button" onClick={loadMachineEnvironment} className="text-indigo-300 hover:text-indigo-200">Retry</button>}
                    </section>
                  )}
                </>
              )}

              {(showAll || activeTab === 'updates') && (
                <section className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3 border-b border-[#4a433e] pb-3">
                    <div className="flex items-center gap-2">
                      <DownloadCloud className="w-4 h-4 text-sky-300" />
                      <div>
                        <h2 className="text-sm font-bold text-slate-200">NouSetsu Desktop Updates</h2>
                        <p className="text-[11px] text-slate-400 mt-1">
                          {isTauriDesktop()
                            ? 'Check, download, and install signed updates without leaving NouSetsu.'
                            : 'Check release information here; install updates from the NouSetsu desktop app.'}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleCheckUpdates}
                      disabled={checkingUpdates || installingUpdate}
                      className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${checkingUpdates ? 'animate-spin' : ''}`} />
                      {checkingUpdates ? 'Checking...' : 'Check for Updates'}
                    </button>
                  </div>

                  {updateError && <p role="alert" className="text-xs text-rose-300">{updateError}</p>}
                  {updateInfo && (
                    <div className="space-y-3 text-xs">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-300">
                        <span>Installed: <strong className="font-mono">{updateInfo.current_version}</strong></span>
                        <span>Latest: <strong className="font-mono">{updateInfo.latest_version}</strong></span>
                        <span className={updateInfo.update_available ? 'text-amber-300 font-semibold' : 'text-emerald-300 font-semibold'}>
                          {updateInfo.update_available ? 'Update available' : 'You are up to date'}
                        </span>
                      </div>
                      <h3 className="font-semibold text-slate-200">{updateInfo.release_name}</h3>
                      <div className="max-h-64 overflow-y-auto rounded-[3px] bg-[#24201d] border border-[#3f3a36] p-3 whitespace-pre-wrap text-slate-300 leading-relaxed">
                        {updateInfo.release_notes}
                      </div>
                      {updateInfo.update_available && desktopUpdate && (
                        <button
                          type="button"
                          onClick={handleInstallUpdate}
                          disabled={installingUpdate}
                          className="btn-primary text-xs inline-flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <DownloadCloud className="w-3.5 h-3.5" />
                          {installingUpdate ? 'Installing update...' : 'Install Update'}
                        </button>
                      )}
                      {updateInfo.update_available && !isTauriDesktop() && (
                        <p className="text-[10px] text-slate-400">
                          Web Studio cannot install updates. Download and run the installer from the{' '}
                          <a
                            href={updateInfo.release_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-indigo-300 hover:text-indigo-200 underline"
                          >
                            latest GitHub release
                          </a>.
                        </p>
                      )}
                      {updateInfo.update_available && isTauriDesktop() && !desktopUpdate && (
                        <p className="text-[10px] text-slate-400">
                          The signed in-app check was unavailable. Download the installer from the{' '}
                          <a
                            href={updateInfo.release_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-indigo-300 hover:text-indigo-200 underline"
                          >
                            latest GitHub release
                          </a>{' '}
                          and run it to update NouSetsu.
                        </p>
                      )}
                      {installingUpdate && (
                        <div role="status" className="space-y-1.5">
                          <div className="flex justify-between text-[10px] text-slate-400">
                            <span>Downloading and installing the signed update...</span>
                            <span>{updateProgress === null ? ' ' : `${updateProgress}%`}</span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded bg-[#24201d]">
                            <div
                              className={`h-full bg-sky-400 transition-all ${updateProgress === null ? 'w-1/3 animate-pulse' : ''}`}
                              style={updateProgress === null ? undefined : { width: `${updateProgress}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  {!updateInfo && !updateError && (
                    <p className="text-xs text-slate-400">
                      {isTauriDesktop()
                        ? 'NouSetsu checks for signed releases and installs updates directly in the app.'
                        : 'In-app updates are available from the installed NouSetsu desktop application.'}
                    </p>
                  )}
                </section>
              )}

              {(showAll || activeTab === 'logs') && (
                <section className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3 border-b border-[#4a433e] pb-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-emerald-300" />
                      <div>
                        <h2 className="text-sm font-bold text-slate-200">Local Logs & Diagnostics</h2>
                        <p className="text-[11px] text-slate-400 mt-1">
                          Persistent rotating log files (up to 10 MB per file, 5 backups) tracking backend execution, frontend errors, and desktop lifecycle.
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={loadLogsInfo}
                        disabled={loadingLogs}
                        className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${loadingLogs ? 'animate-spin' : ''}`} />
                        {loadingLogs ? 'Refreshing...' : 'Refresh'}
                      </button>
                      <button
                        type="button"
                        onClick={handleOpenLogsFolder}
                        disabled={openingLogsFolder}
                        className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <FolderOpen className="w-3.5 h-3.5" />
                        {openingLogsFolder ? 'Opening...' : 'Open Logs Folder'}
                      </button>
                    </div>
                  </div>

                  {logsInfo ? (
                    <div className="space-y-4 text-xs">
                      <div className="rounded-[3px] bg-[#24201d] border border-[#3f3a36] p-3 text-slate-300">
                        <span className="text-slate-400">Log Directory:</span>{' '}
                        <code className="text-[#dad2c1] font-mono select-all ml-1">{logsInfo.logs_dir}</code>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {/* backend.log card */}
                        <div className="rounded-[4px] bg-[#2a2624] border border-[#3f3a36] p-3.5 flex flex-col justify-between space-y-3">
                          <div>
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-sky-300 text-xs">backend.log</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                  logsInfo.files['backend.log']?.exists
                                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                                }`}
                              >
                                {logsInfo.files['backend.log']?.exists ? logsInfo.files['backend.log'].size_display : 'Not Created'}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                              FastAPI server, translation pipeline agents, LLM prompts/responses, rate limiter events, and uncaught crash traces.
                            </p>
                          </div>
                          {logsInfo.files['backend.log']?.modified_time && (
                            <div className="text-[10px] text-slate-500 pt-1 border-t border-[#383330]">
                              Modified: {new Date(logsInfo.files['backend.log'].modified_time * 1000).toLocaleString()}
                            </div>
                          )}
                        </div>

                        {/* frontend.log card */}
                        <div className="rounded-[4px] bg-[#2a2624] border border-[#3f3a36] p-3.5 flex flex-col justify-between space-y-3">
                          <div>
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-emerald-300 text-xs">frontend.log</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                  logsInfo.files['frontend.log']?.exists
                                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                                }`}
                              >
                                {logsInfo.files['frontend.log']?.exists ? logsInfo.files['frontend.log'].size_display : 'Not Created'}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                              Web UI runtime console warnings, errors, and unhandled window exceptions forwarded from the browser/webview.
                            </p>
                          </div>
                          {logsInfo.files['frontend.log']?.modified_time && (
                            <div className="text-[10px] text-slate-500 pt-1 border-t border-[#383330]">
                              Modified: {new Date(logsInfo.files['frontend.log'].modified_time * 1000).toLocaleString()}
                            </div>
                          )}
                        </div>

                        {/* desktop.log card */}
                        <div className="rounded-[4px] bg-[#2a2624] border border-[#3f3a36] p-3.5 flex flex-col justify-between space-y-3">
                          <div>
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-purple-300 text-xs">desktop.log</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                  logsInfo.files['desktop.log']?.exists
                                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                                }`}
                              >
                                {logsInfo.files['desktop.log']?.exists ? logsInfo.files['desktop.log'].size_display : 'Not Created'}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                              Tauri desktop launcher initialization, install path resolution, sidecar process PID, health check status, and shutdown.
                            </p>
                          </div>
                          {logsInfo.files['desktop.log']?.modified_time && (
                            <div className="text-[10px] text-slate-500 pt-1 border-t border-[#383330]">
                              Modified: {new Date(logsInfo.files['desktop.log'].modified_time * 1000).toLocaleString()}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400">
                      {loadingLogs ? 'Loading logs status...' : 'Click "Refresh" to view log file sizes and statuses.'}
                    </div>
                  )}
                </section>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
