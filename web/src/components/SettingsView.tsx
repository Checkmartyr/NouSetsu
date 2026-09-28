import React, { useState, useEffect } from 'react';
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
  ExternalLink,
  DownloadCloud,
} from 'lucide-react';
import { MachineEnvironment, ProjectSettings, UpdateCheckResult } from '../types/dashboard';
import {
  checkLatestRelease,
  fetchMachineEnvironment,
  fetchSettings,
  saveMachineEnvironment,
  updateSettings,
} from '../services/dashboardApi';

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
  { id: 'updates', name: 'App Updates', shortDesc: 'Check GitHub releases', icon: Download, group: 'global' },
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

const GLOBAL_ENV_GROUPS: Record<string, { title: string; keys: string[] }> = {
  general: { title: 'Language Defaults', keys: ['SOURCE_LANG', 'TARGET_LANG'] },
  models: {
    title: 'Model & Generation Defaults',
    keys: [
      'DEFAULT_MODEL', 'NOVEL_MODEL', 'NOVEL_FALLBACK_MODEL',
      'NOVEL_EXTRACTOR_MODEL', 'NOVEL_DRAFTER_MODEL', 'NOVEL_CRITIC_MODEL',
      'NOVEL_POLISHER_MODEL', 'NOVEL_CHRONICLER_MODEL',
      'NOVEL_THINKING_LEVEL', 'NOVEL_EXTRACTOR_THINKING_LEVEL',
      'NOVEL_DRAFTER_THINKING_LEVEL', 'NOVEL_CRITIC_THINKING_LEVEL',
      'NOVEL_POLISHER_THINKING_LEVEL', 'NOVEL_CHRONICLER_THINKING_LEVEL',
      'NOVEL_THINKING_BUDGET', 'NOVEL_EXTRACTOR_THINKING_BUDGET',
      'NOVEL_DRAFTER_THINKING_BUDGET', 'NOVEL_CRITIC_THINKING_BUDGET',
      'NOVEL_POLISHER_THINKING_BUDGET', 'NOVEL_CHRONICLER_THINKING_BUDGET',
      'NOVEL_TEMPERATURE', 'NOVEL_USE_INTERACTIONS',
    ],
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

const API_KEY_LABELS = [
  { key: 'GEMINI_API_KEY', label: 'Gemini API key' },
  { key: 'GOOGLE_API_KEY', label: 'Google API key (Gemini alias)' },
  { key: 'OPENAI_API_KEY', label: 'OpenAI API key' },
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter API key' },
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
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResult | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);

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

  useEffect(() => {
    loadSettingsData();
  }, [activeProjectPath]);

  useEffect(() => {
    loadMachineEnvironment();
  }, []);


  const handleLoadEnvPresets = () => {
    if (!settings) return;
    const envPres = settings.env_presets || {};
    setSettings({
      ...settings,
      model_name: envPres.model_name || settings.env?.NOVEL_MODEL || 'gemini-3.1-flash-lite',
      fallback_model: envPres.fallback_model || settings.env?.NOVEL_FALLBACK_MODEL || 'gemini-3.5-flash-lite',
      extractor_model: envPres.extractor_model || 'gemini-3.1-flash-lite',
      drafter_model: envPres.drafter_model || 'gemini-3.5-flash-lite',
      critic_model: envPres.critic_model || 'gemma-4-26b-a4b-it',
      polisher_model: envPres.polisher_model || 'gemini-3.5-flash-lite',
      chronicler_model: envPres.chronicler_model || 'gemma-4-26b-a4b-it',
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
      await loadMachineEnvironment();
      showToast('Local environment settings saved.');
    } else {
      alert('Could not save the local .env settings.');
    }
  };

  const handleCheckUpdates = async () => {
    setCheckingUpdates(true);
    setUpdateError(null);
    try {
      setUpdateInfo(await checkLatestRelease());
    } catch (error) {
      setUpdateError(error instanceof Error ? error.message : 'Could not check for updates.');
    } finally {
      setCheckingUpdates(false);
    }
  };

  const renderMachineEnvironmentSection = (groupId: string, group: { title: string; keys: string[] }) => {
    if (!machineEnvironment) return null;

    return (
      <section key={groupId} className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5 space-y-4">
        <div className="flex items-center gap-2 border-b border-[#4a433e] pb-3">
          <KeyRound className="w-4 h-4 text-amber-300" />
          <div>
            <h2 className="text-sm font-bold text-slate-200">{group.title}</h2>
            <p className="text-[11px] text-slate-400 mt-1">Machine defaults saved in the local .env file.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {group.keys.map((key) => (
            <label key={key} className="block min-w-0">
              <span className="block text-slate-400 mb-1 font-mono">{key}</span>
              <input
                type="text"
                value={machineEnvironment.values[key] || ''}
                onChange={(event) => setMachineEnvironment((current) => current ? {
                  ...current,
                  values: { ...current.values, [key]: event.target.value },
                } : current)}
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
              />
            </label>
          ))}
        </div>

        {groupId === 'models' && (
          <div className="border-t border-[#4a433e] pt-4 space-y-3">
            <div>
              <h3 className="text-xs font-semibold text-slate-200">Provider API keys</h3>
              <p className="text-[10px] text-slate-400 mt-1">Keys are stored locally and never returned to the browser. Leave blank to keep a saved key; status reflects this .env file.</p>

            </div>
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
        if (activeTab === 'updates') return;
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
                  : `Project Settings: ${settings?.title || activeProjectTitle || 'No project selected'}`}
            </h1>
          </div>
          <p className="text-xs text-[#aea69c] mt-0.5">
            {activeTab === 'global'
              ? 'Machine-wide defaults and provider credentials shared across projects.'
              : activeTab === 'updates'
                ? 'Check for NouSetsu desktop releases.'
                : <>Project-specific options are saved in <code className="text-[#dad2c1] font-mono">.novel/config.yaml</code>.</>}
          </p>
        </div>

        {!['global', 'updates'].includes(activeTab) && (
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
                      <input
                        type="text"
                        list="model-suggestions"
                        value={settings.model_name || ''}
                        onChange={(e) => setSettings({ ...settings, model_name: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                        placeholder={settings.env_presets?.model_name || 'gemini-3.1-flash-lite'}
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
                        Automatic failover model when primary LLM encounters HTTP 429 quota exhaustion.
                      </p>
                      <input
                        type="text"
                        list="model-suggestions"
                        value={settings.fallback_model || ''}
                        onChange={(e) => setSettings({ ...settings, fallback_model: e.target.value })}
                        className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                        placeholder={settings.env_presets?.fallback_model || 'gemini-3.5-flash-lite'}
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

                  {/* Gemini Interactions API Toggle */}
                  <div className="flex items-center justify-between bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 text-xs">
                    <div>
                      <div className="font-semibold text-slate-200">Use Gemini Interactions API</div>
                      <div className="text-[11px] text-slate-400">
                        Routes Gemini models to Google's native <code className="text-slate-300 font-mono">/v1beta/interactions</code> endpoint for granular thought tokens.
                      </div>
                    </div>
                    <ToggleSwitch
                      checked={settings.use_interactions_api !== false}
                      onChange={(val) => setSettings({ ...settings, use_interactions_api: val })}
                    />
                  </div>

                  {/* Five Pipeline Agent Roles */}
                  <div className="space-y-3 pt-2">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                      Five Pipeline Agent Overrides
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      {/* Stage 1: Extractor */}
                      <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded text-[10px] font-semibold">
                              Stage 1
                            </span>
                            <label className="font-semibold text-slate-200">Entity Extractor Agent</label>
                          </div>
                          {settings.extractor_model && (
                            <button
                              type="button"
                              onClick={() => setSettings({ ...settings, extractor_model: '' })}
                              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                            >
                              <X className="w-3 h-3" /> Clear
                            </button>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-400">
                          The Detective: Analyzes raw text before drafting to discover unknown terms & entities.
                        </p>
                        <input
                          type="text"
                          list="model-suggestions"
                          value={settings.extractor_model || ''}
                          onChange={(e) => setSettings({ ...settings, extractor_model: e.target.value })}
                          className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                          placeholder={settings.env_presets?.extractor_model || settings.effective_extractor_model || 'gemini-3.1-flash-lite'}
                        />
                        <div className="flex items-center justify-between text-[10px] text-slate-500">
                          <span>
                            Active:{' '}
                            <strong className="text-slate-400 font-mono">
                              {settings.extractor_model || settings.effective_extractor_model || 'gemini-3.1-flash-lite'}
                            </strong>
                          </span>
                          {settings.extractor_model ? (
                            <span className="text-purple-400 font-medium">Project Override</span>
                          ) : (
                            <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                          )}
                        </div>
                      </div>

                      {/* Stage 2: Drafter */}
                      <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 rounded text-[10px] font-semibold">
                              Stage 2
                            </span>
                            <label className="font-semibold text-slate-200">Context-Aware Drafter Agent</label>
                          </div>
                          {settings.drafter_model && (
                            <button
                              type="button"
                              onClick={() => setSettings({ ...settings, drafter_model: '' })}
                              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                            >
                              <X className="w-3 h-3" /> Clear
                            </button>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-400">
                          The Wordsmith: Resolves zero-anaphora and produces initial full literary draft.
                        </p>
                        <input
                          type="text"
                          list="model-suggestions"
                          value={settings.drafter_model || ''}
                          onChange={(e) => setSettings({ ...settings, drafter_model: e.target.value })}
                          className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                          placeholder={settings.env_presets?.drafter_model || settings.effective_drafter_model || 'gemini-3.5-flash-lite'}
                        />
                        <div className="flex items-center justify-between text-[10px] text-slate-500">
                          <span>
                            Active:{' '}
                            <strong className="text-slate-400 font-mono">
                              {settings.drafter_model || settings.effective_drafter_model || 'gemini-3.5-flash-lite'}
                            </strong>
                          </span>
                          {settings.drafter_model ? (
                            <span className="text-purple-400 font-medium">Project Override</span>
                          ) : (
                            <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                          )}
                        </div>
                      </div>

                      {/* Stage 3: Critic */}
                      <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-rose-500/10 text-rose-400 rounded text-[10px] font-semibold">
                              Stage 3
                            </span>
                            <label className="font-semibold text-slate-200">Critique & Auditor Agent</label>
                          </div>
                          {settings.critic_model && (
                            <button
                              type="button"
                              onClick={() => setSettings({ ...settings, critic_model: '' })}
                              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                            >
                              <X className="w-3 h-3" /> Clear
                            </button>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-400">
                          The Inspector: Line-by-line auditor scoring fidelity and detecting omissions.
                        </p>
                        <input
                          type="text"
                          list="model-suggestions"
                          value={settings.critic_model || ''}
                          onChange={(e) => setSettings({ ...settings, critic_model: e.target.value })}
                          className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                          placeholder={settings.env_presets?.critic_model || settings.effective_critic_model || 'gemma-4-26b-a4b-it'}
                        />
                        <div className="flex items-center justify-between text-[10px] text-slate-500">
                          <span>
                            Active:{' '}
                            <strong className="text-slate-400 font-mono">
                              {settings.critic_model || settings.effective_critic_model || 'gemma-4-26b-a4b-it'}
                            </strong>
                          </span>
                          {settings.critic_model ? (
                            <span className="text-purple-400 font-medium">Project Override</span>
                          ) : (
                            <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                          )}
                        </div>
                      </div>

                      {/* Stage 4: Polisher */}
                      <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded text-[10px] font-semibold">
                              Stage 4
                            </span>
                            <label className="font-semibold text-slate-200">Prose Polishing Agent</label>
                          </div>
                          {settings.polisher_model && (
                            <button
                              type="button"
                              onClick={() => setSettings({ ...settings, polisher_model: '' })}
                              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                            >
                              <X className="w-3 h-3" /> Clear
                            </button>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-400">
                          The Stylist: Refines drafted prose into publication-quality English prose.
                        </p>
                        <input
                          type="text"
                          list="model-suggestions"
                          value={settings.polisher_model || ''}
                          onChange={(e) => setSettings({ ...settings, polisher_model: e.target.value })}
                          className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                          placeholder={settings.env_presets?.polisher_model || settings.effective_polisher_model || 'gemini-3.5-flash-lite'}
                        />
                        <div className="flex items-center justify-between text-[10px] text-slate-500">
                          <span>
                            Active:{' '}
                            <strong className="text-slate-400 font-mono">
                              {settings.polisher_model || settings.effective_polisher_model || 'gemini-3.5-flash-lite'}
                            </strong>
                          </span>
                          {settings.polisher_model ? (
                            <span className="text-purple-400 font-medium">Project Override</span>
                          ) : (
                            <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                          )}
                        </div>
                      </div>

                      {/* Stage 5: Chronicler */}
                      <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5 md:col-span-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[10px] font-semibold">
                              Stage 5
                            </span>
                            <label className="font-semibold text-slate-200">Chronicler Lore Memory Agent</label>
                          </div>
                          {settings.chronicler_model && (
                            <button
                              type="button"
                              onClick={() => setSettings({ ...settings, chronicler_model: '' })}
                              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-0.5"
                            >
                              <X className="w-3 h-3" /> Clear
                            </button>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-400">
                          The Memory Keeper: Synthesizes 3-tier narrative memory, arc summaries, and reconciles terms.
                        </p>
                        <input
                          type="text"
                          list="model-suggestions"
                          value={settings.chronicler_model || ''}
                          onChange={(e) => setSettings({ ...settings, chronicler_model: e.target.value })}
                          className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                          placeholder={settings.env_presets?.chronicler_model || settings.effective_chronicler_model || 'gemma-4-26b-a4b-it'}
                        />
                        <div className="flex items-center justify-between text-[10px] text-slate-500">
                          <span>
                            Active:{' '}
                            <strong className="text-slate-400 font-mono">
                              {settings.chronicler_model || settings.effective_chronicler_model || 'gemma-4-26b-a4b-it'}
                            </strong>
                          </span>
                          {settings.chronicler_model ? (
                            <span className="text-purple-400 font-medium">Project Override</span>
                          ) : (
                            <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                          )}
                        </div>
                      </div>
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
                      {Object.entries(GLOBAL_ENV_GROUPS).map(([groupId, group]) =>
                        renderMachineEnvironmentSection(groupId, group)
                      )}
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
                        <p className="text-[11px] text-slate-400 mt-1">Check the latest published GitHub release tag and download its installer.</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleCheckUpdates}
                      disabled={checkingUpdates}
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
                      <div className="flex flex-wrap items-center gap-3">
                        <a href={updateInfo.release_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-300 hover:text-indigo-200">
                          Open GitHub release <ExternalLink className="w-3 h-3" />
                        </a>
                        {updateInfo.assets.map((asset) => (
                          <a key={asset.download_url} href={asset.download_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-300 hover:text-indigo-200">
                            Download {asset.name} <ExternalLink className="w-3 h-3" />
                          </a>
                        ))}
                      </div>
                      <p className="text-[10px] text-slate-500">Install the downloaded release manually; its installer updates the frontend and bundled Python backend together. Silent in-app installation requires signed Tauri updater artifacts, which are not configured for this project yet.</p>
                    </div>
                  )}
                  {!updateInfo && !updateError && <p className="text-xs text-slate-400">The release checker compares the latest GitHub release tag with this desktop app version.</p>}
                </section>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
