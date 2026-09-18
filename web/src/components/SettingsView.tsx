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
} from 'lucide-react';
import { ProjectSettings } from '../types/dashboard';
import { fetchSettings, updateSettings } from '../services/dashboardApi';

interface SettingsViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
  onProjectUpdated?: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
  onProjectUpdated,
}) => {
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectPath || !settings) return;
    setSaving(true);
    // Exclude nested stale config and env snapshots before sending to backend
    const { config, env, ...cleanSettings } = settings;
    const sanitizedSettings = {
      ...cleanSettings,
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

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
      {/* Toast */}
      {toast && (
        <div className="fixed top-20 right-8 z-50 px-4 py-2 bg-emerald-600 text-white rounded-lg shadow-xl text-sm font-medium flex items-center gap-2">
          <Check className="w-4 h-4" />
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-indigo-400" />
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Project Settings: {settings?.title || activeProjectTitle}
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Configure LLM cascade models, review loop parameters, and semantic chunking.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || !settings}
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      {/* Settings Form Body */}
      <div className="flex-1 overflow-y-auto p-6 flex justify-center">
        {loading || !settings ? (
          <div className="text-center py-20 text-slate-500">Loading settings...</div>
        ) : (
          <form onSubmit={handleSave} className="max-w-3xl w-full space-y-6 pb-12">
            {/* Section 1: General Novel Metadata */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                <Sliders className="w-4 h-4 text-indigo-400" />
                <h2 className="text-sm font-bold text-slate-200">Novel Information</h2>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Novel Title</label>
                  <input
                    type="text"
                    value={settings.title || ''}
                    onChange={(e) => setSettings({ ...settings, title: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Genre</label>
                  <input
                    type="text"
                    value={settings.genre || ''}
                    onChange={(e) => setSettings({ ...settings, genre: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                    placeholder="isekai, xianxia, litrpg, romance..."
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Source Language</label>
                  <input
                    type="text"
                    value={settings.source_language || ''}
                    onChange={(e) =>
                      setSettings({ ...settings, source_language: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Target Language</label>
                  <input
                    type="text"
                    value={settings.target_language || ''}
                    onChange={(e) =>
                      setSettings({ ...settings, target_language: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>
            </div>

            {/* Section 2: Multi-Agent Model Routing & Presets */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
                <div className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-purple-400" />
                  <div>
                    <h2 className="text-sm font-bold text-slate-200">
                      Multi-Agent Model Routing & Fallback Cascade
                    </h2>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Configure specialized LLMs per pipeline stage or load presets based on your .env configuration.
                    </p>
                  </div>
                </div>

                {/* Presets Toolbar */}
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Preset Selector Dropdown */}
                  <select
                    onChange={(e) => {
                      handleApplyPreset(e.target.value);
                      e.target.value = '';
                    }}
                    defaultValue=""
                    className="bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
                  >
                    <option value="" disabled>
                      ⚡ Apply Preset Profile...
                    </option>
                    {settings.available_presets?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>

                  {/* Load .env Presets Quick Button */}
                  <button
                    type="button"
                    onClick={handleLoadEnvPresets}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 hover:border-purple-500/50 rounded-lg text-xs font-medium cursor-pointer transition-all shadow-sm"
                    title="Load model defaults configured in your machine's .env file into the form"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Load .env Presets
                  </button>

                  {/* Clear All Overrides Button */}
                  <button
                    type="button"
                    onClick={handleClearOverrides}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium cursor-pointer transition-all"
                    title="Clear all project overrides so all agents inherit dynamically from .env"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Clear Overrides
                  </button>
                </div>
              </div>

              {/* Datalist for Model Autocomplete Suggestions */}
              <datalist id="model-suggestions">
                {(
                  settings.model_catalog || [
                    'gemini-3.1-flash-lite',
                    'gemini-3.5-flash-lite',
                    'gemini-3.1-pro',
                    'gemma-4-26b-a4b-it',
                    'gemma-4-31b-it',
                  ]
                ).map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>

              {/* Subsection A: Global Primary & Fallback Pipeline Models */}
              <div>
                <div className="flex items-center gap-1.5 mb-2.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
                    Global Pipeline Models
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Primary Production Model */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="font-semibold text-slate-300">
                        Default Production Model
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
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.model_name || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, model_name: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.model_name ||
                        settings.env?.NOVEL_MODEL ||
                        'gemini-3.1-flash-lite'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.model_name ||
                            settings.effective_model_name ||
                            settings.env_presets?.model_name ||
                            'gemini-3.1-flash-lite'}
                        </strong>
                      </span>
                      {settings.model_name ? (
                        <span className="text-purple-400 font-medium">Project Override</span>
                      ) : (
                        <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                      )}
                    </div>
                  </div>

                  {/* 429 / Safety Fallback Model */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="font-semibold text-slate-300">
                        Global 429 / Safety Fallback
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
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.fallback_model || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, fallback_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.fallback_model ||
                        settings.env?.NOVEL_FALLBACK_MODEL ||
                        'gemini-3.5-flash-lite'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.fallback_model ||
                            settings.effective_fallback_model ||
                            settings.env_presets?.fallback_model ||
                            'gemini-3.5-flash-lite'}
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
              </div>

              {/* Subsection B: Specialized 5-Agent Routing Matrix */}
              <div>
                <div className="flex items-center gap-1.5 mb-2.5">
                  <Bot className="w-3.5 h-3.5 text-purple-400" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
                    Specialized Agent Routing (LangGraph Pipeline)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Stage 1: Entity Extractor */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded text-[10px] font-semibold">
                          Stage 1
                        </span>
                        <label className="font-semibold text-slate-200">
                          Entity Extractor Agent
                        </label>
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
                      The Detective: Discovers unknown characters, realms, and terms before drafting.
                    </p>
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.extractor_model || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, extractor_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.extractor_model ||
                        settings.effective_extractor_model ||
                        'gemini-3.1-flash-lite'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.extractor_model ||
                            settings.effective_extractor_model ||
                            settings.env_presets?.extractor_model ||
                            'gemini-3.1-flash-lite'}
                        </strong>
                      </span>
                      {settings.extractor_model ? (
                        <span className="text-purple-400 font-medium">Project Override</span>
                      ) : (
                        <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 2: Context-Aware Drafter */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-[10px] font-semibold">
                          Stage 2
                        </span>
                        <label className="font-semibold text-slate-200">
                          Context-Aware Drafter Agent
                        </label>
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
                      The Wordsmith: Produces first translation draft and resolves zero-anaphora.
                    </p>
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.drafter_model || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, drafter_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.drafter_model ||
                        settings.effective_drafter_model ||
                        'gemini-3.5-flash-lite'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.drafter_model ||
                            settings.effective_drafter_model ||
                            settings.env_presets?.drafter_model ||
                            'gemini-3.5-flash-lite'}
                        </strong>
                      </span>
                      {settings.drafter_model ? (
                        <span className="text-purple-400 font-medium">Project Override</span>
                      ) : (
                        <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 3: Critique Agent */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 rounded text-[10px] font-semibold">
                          Stage 3
                        </span>
                        <label className="font-semibold text-slate-200">
                          Critique Agent & Quality Auditor
                        </label>
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
                      The Inspector: Line-by-line fidelity and style scoring (0–10) against source text.
                    </p>
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.critic_model || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, critic_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.critic_model ||
                        settings.effective_critic_model ||
                        'gemma-4-26b-a4b-it'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.critic_model ||
                            settings.effective_critic_model ||
                            settings.env_presets?.critic_model ||
                            'gemma-4-26b-a4b-it'}
                        </strong>
                      </span>
                      {settings.critic_model ? (
                        <span className="text-purple-400 font-medium">Project Override</span>
                      ) : (
                        <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 4: Polishing Agent */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 bg-pink-500/10 text-pink-400 rounded text-[10px] font-semibold">
                          Stage 4
                        </span>
                        <label className="font-semibold text-slate-200">
                          Prose Polishing Agent
                        </label>
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
                      The Stylist: Rewrites prose into publication-grade English with Diff/Patch optimization.
                    </p>
                    <input
                      type="text"
                      list="model-suggestions"
                      value={settings.polisher_model || ''}
                      onChange={(e) =>
                        setSettings({ ...settings, polisher_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.polisher_model ||
                        settings.effective_polisher_model ||
                        'gemini-3.5-flash-lite'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.polisher_model ||
                            settings.effective_polisher_model ||
                            settings.env_presets?.polisher_model ||
                            'gemini-3.5-flash-lite'}
                        </strong>
                      </span>
                      {settings.polisher_model ? (
                        <span className="text-purple-400 font-medium">Project Override</span>
                      ) : (
                        <span className="text-emerald-400 font-medium">Inheriting from .env</span>
                      )}
                    </div>
                  </div>

                  {/* Stage 5: Chronicler Agent */}
                  <div className="bg-slate-950/40 border border-slate-800/80 rounded-lg p-3 space-y-1.5 md:col-span-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[10px] font-semibold">
                          Stage 5
                        </span>
                        <label className="font-semibold text-slate-200">
                          Chronicler Lore Memory Agent
                        </label>
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
                      onChange={(e) =>
                        setSettings({ ...settings, chronicler_model: e.target.value })
                      }
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                      placeholder={
                        settings.env_presets?.chronicler_model ||
                        settings.effective_chronicler_model ||
                        'gemma-4-26b-a4b-it'
                      }
                    />
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>
                        Active:{' '}
                        <strong className="text-slate-400 font-mono">
                          {settings.chronicler_model ||
                            settings.effective_chronicler_model ||
                            settings.env_presets?.chronicler_model ||
                            'gemma-4-26b-a4b-it'}
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

            {/* Section 3: Reflection Review & Quality Controls */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                <RefreshCw className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-bold text-slate-200">
                  LangGraph Reflection Review Cycle
                </h2>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">
                    Max Review Loops ({settings.max_review_loops ?? 2})
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={5}
                    value={settings.max_review_loops ?? 2}
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
                    <span>2 (Standard)</span>
                    <span>3 (Rigorous)</span>
                    <span>5 (Exhaustive)</span>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">
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
            </div>

            {/* Section 4: Semantic Chunking Parameters */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                <Layers className="w-4 h-4 text-pink-400" />
                <h2 className="text-sm font-bold text-slate-200">
                  Line-Based Semantic Chunking
                </h2>
              </div>

              <div className="grid grid-cols-3 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Chunk Size (lines)</label>
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Section 5: Directory Paths */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                <Folder className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-bold text-slate-200">Workspace Paths</h2>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                <div>
                  <label className="block text-slate-400 mb-1">
                    Raw Chapters Directory
                  </label>
                  <input
                    type="text"
                    value={settings.raw_dir || ''}
                    onChange={(e) => setSettings({ ...settings, raw_dir: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">
                    Translated Chapters Directory
                  </label>
                  <input
                    type="text"
                    value={settings.translated_dir || ''}
                    onChange={(e) =>
                      setSettings({ ...settings, translated_dir: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  />
                </div>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
