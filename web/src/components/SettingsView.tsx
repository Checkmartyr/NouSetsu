import React, { useState, useEffect } from 'react';
import {
  Settings,
  Cpu,
  RefreshCw,
  Layers,
  Save,
  Check,
  Folder,
  Sliders
} from 'lucide-react';
import { ProjectSettings } from '../types/dashboard';
import { fetchSettings, updateSettings } from '../services/dashboardApi';

interface SettingsViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectPath || !settings) return;
    setSaving(true);
    const success = await updateSettings(settings, activeProjectPath);
    setSaving(false);
    if (success) {
      showToast('Settings saved to config.yaml successfully!');
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
                    value={settings.title}
                    onChange={(e) => setSettings({ ...settings, title: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Genre</label>
                  <input
                    type="text"
                    value={settings.genre}
                    onChange={(e) => setSettings({ ...settings, genre: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                    placeholder="isekai, xianxia, litrpg, romance..."
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Source Language</label>
                  <input
                    type="text"
                    value={settings.source_language}
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
                    value={settings.target_language}
                    onChange={(e) =>
                      setSettings({ ...settings, target_language: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>
            </div>

            {/* Section 2: Model Cascade Configuration */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3">
                <Cpu className="w-4 h-4 text-purple-400" />
                <h2 className="text-sm font-bold text-slate-200">
                  Model Precedence & Fallback Cascade
                </h2>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">
                    Primary Production Model
                  </label>
                  <input
                    type="text"
                    value={settings.model_name}
                    onChange={(e) =>
                      setSettings({ ...settings, model_name: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    placeholder="gemini-3.1-flash-lite, gemma-4-26b-a4b-it"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Used for primary drafter, polisher, and chronicler stages.
                  </span>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">
                    429 / Safety Fallback Model
                  </label>
                  <input
                    type="text"
                    value={settings.fallback_model}
                    onChange={(e) =>
                      setSettings({ ...settings, fallback_model: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                    placeholder="gemini-3.5-flash-lite"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Automatic failover when primary model hits rate limit or errors.
                  </span>
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
                    Max Review Loops ({settings.max_review_loops})
                  </label>
                  <input
                    type="range"
                    min={1}
                    max={5}
                    value={settings.max_review_loops}
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
                    Quality Score Threshold ({settings.quality_threshold})
                  </label>
                  <input
                    type="range"
                    min={6.0}
                    max={9.5}
                    step={0.1}
                    value={settings.quality_threshold}
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
                    value={settings.chunk_threshold_lines}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        chunk_threshold_lines: parseInt(e.target.value, 10) || 85,
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Chunk Size (lines)</label>
                  <input
                    type="number"
                    value={settings.chunk_size_lines}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        chunk_size_lines: parseInt(e.target.value, 10) || 70,
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">
                    Chunk Overlap (lines)
                  </label>
                  <input
                    type="number"
                    value={settings.chunk_overlap_lines}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        chunk_overlap_lines: parseInt(e.target.value, 10) || 3,
                      })
                    }
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
                    value={settings.raw_dir}
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
                    value={settings.translated_dir}
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
