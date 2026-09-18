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
} from 'lucide-react';
import { ProjectSettings } from '../types/dashboard';
import { fetchSettings, updateSettings } from '../services/dashboardApi';

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
}

const SETTING_CATEGORIES: SettingCategory[] = [
  { id: 'all', name: 'All Settings', shortDesc: 'Continuous full view', icon: LayoutGrid },
  { id: 'general', name: 'Novel Information', shortDesc: 'Metadata, title & language', icon: Sliders },
  { id: 'models', name: 'Model Routing', shortDesc: '5 Agents & LLM cascades', icon: Cpu },
  { id: 'review', name: 'Review & Quality', shortDesc: 'Reflection loops & Diff patch', icon: RefreshCw },
  { id: 'chunking', name: 'Semantic Chunking', shortDesc: 'Line-based text chunking', icon: Layers },
  { id: 'memory', name: 'Memory & Bible', shortDesc: 'Cross-folder & reconciliation', icon: BookMarked },
  { id: 'rag', name: 'Episodic Lore & RAG', shortDesc: 'Tier 4 SQLite hybrid retrieval', icon: Sparkles },
  { id: 'safety', name: 'Safety & Bisection', shortDesc: 'Recursive safety bisection', icon: ShieldAlert },
  { id: 'ratelimit', name: 'Rate Limits & Quota', shortDesc: '32k TPM / 60 RPM guard', icon: Zap },
  { id: 'paths', name: 'Workspace Paths', shortDesc: 'Raw & translated directories', icon: Folder },
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
    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed ${
      checked ? 'bg-indigo-600' : 'bg-slate-800'
    }`}
  >
    <span
      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
        checked ? 'translate-x-4' : 'translate-x-0'
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

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const loadSettingsData = async () => {
    if (!activeProjectPath) return;
    setLoading(true);
    const data = await fetchSettings(activeProjectPath);
    setSettings(data);
    setLoading(false);
  };

  useEffect(() => {
    loadSettingsData();
  }, [activeProjectPath]);

  // Keyboard shortcut: Ctrl+S or Cmd+S to save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [settings, activeProjectPath]);

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
    const { config, env, ...cleanSettings } = settings;
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

  const filteredCategories = SETTING_CATEGORIES.filter((cat) => {
    if (!categorySearch.trim()) return true;
    const q = categorySearch.toLowerCase();
    return cat.name.toLowerCase().includes(q) || cat.shortDesc.toLowerCase().includes(q);
  });

  const showAll = activeTab === 'all';

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-20 right-8 z-50 px-4 py-2 bg-emerald-600 text-white rounded-lg shadow-xl text-sm font-medium flex items-center gap-2 animate-fade-in">
          <Check className="w-4 h-4" />
          {toast}
        </div>
      )}

      {/* Header Bar */}
      <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-3.5 flex items-center justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Project Settings: {settings?.title || activeProjectTitle}
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Manage full <code className="text-slate-300 font-mono">.novel/config.yaml</code> settings across all pipeline subsystems.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-block text-[11px] text-slate-500 font-mono">
            Press <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">Ctrl+S</kbd> to save
          </span>
          <button
            onClick={() => handleSave()}
            disabled={saving || !settings}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Settings Groups */}
        <aside className="w-64 bg-slate-900/40 border-r border-slate-800 flex flex-col shrink-0">
          {/* Quick Search */}
          <div className="p-3 border-b border-slate-800/80">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={categorySearch}
                onChange={(e) => setCategorySearch(e.target.value)}
                placeholder="Search settings..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500 placeholder:text-slate-600"
              />
              {categorySearch && (
                <button
                  onClick={() => setCategorySearch('')}
                  className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Navigation Category List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredCategories.map((cat) => {
              const Icon = cat.icon;
              const isActive = activeTab === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveTab(cat.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-2.5 group cursor-pointer ${
                    isActive
                      ? 'bg-indigo-600/15 border border-indigo-500/30 text-white'
                      : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-transparent'
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 shrink-0 transition-colors ${
                      isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className={`text-xs font-semibold truncate ${isActive ? 'text-indigo-200' : ''}`}>
                      {cat.name}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate">{cat.shortDesc}</div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Sidebar Footer info */}
          <div className="p-3 border-t border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Project ID:</span>
            <span className="font-mono text-slate-400 truncate max-w-[120px]">
              {settings?.project_id || 'default_project'}
            </span>
          </div>
        </aside>

        {/* Right Content Area: Form Panes */}
        <main className="flex-1 overflow-y-auto p-6 flex justify-center bg-slate-950">
          {loading || !settings ? (
            <div className="text-center py-20 text-slate-500">Loading settings...</div>
          ) : (
            <form onSubmit={handleSave} className="max-w-4xl w-full space-y-6 pb-16">
              {/* Group 1: General Novel Information */}
              {(showAll || activeTab === 'general') && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="Ascendance of a Bookworm"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Genre</label>
                      <input
                        type="text"
                        value={settings.genre || ''}
                        onChange={(e) => setSettings({ ...settings, genre: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="isekai, xianxia, litrpg, romance..."
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Source Language</label>
                      <input
                        type="text"
                        value={settings.source_language || ''}
                        onChange={(e) => setSettings({ ...settings, source_language: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="Japanese, Chinese, Korean, English..."
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Target Language</label>
                      <input
                        type="text"
                        value={settings.target_language || ''}
                        onChange={(e) => setSettings({ ...settings, target_language: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                        placeholder="English, Thai, French, Spanish..."
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-slate-400 mb-1 font-medium">Project Identifier</label>
                      <input
                        type="text"
                        value={settings.project_id || ''}
                        onChange={(e) => setSettings({ ...settings, project_id: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-400 font-mono text-xs focus:outline-none focus:border-indigo-500"
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
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-5">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-5">
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
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        placeholder="85"
                        value={settings.chunk_threshold_lines === '' ? '' : (settings.chunk_threshold_lines ?? 85)}
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
                            setSettings({ ...settings, chunk_threshold_lines: 85 });
                          }
                        }}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Minimum non-empty lines to trigger chunking</span>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Chunk Size (lines)</label>
                      <input
                        type="number"
                        min={1}
                        placeholder="70"
                        value={settings.chunk_size_lines === '' ? '' : (settings.chunk_size_lines ?? 70)}
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
                            setSettings({ ...settings, chunk_size_lines: 70 });
                          }
                        }}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Preceding context lines passed forward</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 5: Narrative Memory & Novel Bible */}
              {(showAll || activeTab === 'memory') && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Leave blank for default (gemini-3.5-flash-lite)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 7: AI Safety & Bisection Engine */}
              {(showAll || activeTab === 'safety') && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">Maximum bisection recursion tree depth (default: 4)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 8: Rate Limiting & Quota Guard */}
              {(showAll || activeTab === 'ratelimit') && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-[10px] text-slate-500">60-second sliding window RPM limit (default: 60)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Group 9: Directory Paths */}
              {(showAll || activeTab === 'paths') && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-indigo-500"
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
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-indigo-500"
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
            </form>
          )}
        </main>
      </div>
    </div>
  );
};
