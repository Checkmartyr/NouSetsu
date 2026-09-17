import React, { useState } from 'react';
import { X, Sparkles, FolderPlus } from 'lucide-react';
import { createProject } from '../services/apiClient';
import { ProjectMeta } from '../types/trace';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: ProjectMeta) => void;
  projectsDirName?: string;
}

export const NewProjectModal: React.FC<NewProjectModalProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
  projectsDirName = 'project',
}) => {
  const [title, setTitle] = useState('');
  const [folderName, setFolderName] = useState('');
  const [sourceLanguage, setSourceLanguage] = useState('Japanese');
  const [targetLanguage, setTargetLanguage] = useState('Thai');
  const [genre, setGenre] = useState('general');
  const [model, setModel] = useState('gemini-3.5-flash-lite');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMsg('Please enter a novel title.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await createProject({
        title: title.trim(),
        folder_name: folderName.trim() || undefined,
        source_language: sourceLanguage.trim() || 'Japanese',
        target_language: targetLanguage.trim() || 'Thai',
        genre: genre.trim() || 'general',
        model: model.trim() || undefined,
      });

      if (res.success && res.active_project) {
        onProjectCreated(res.active_project);
        onClose();
      } else {
        setErrorMsg('Project creation did not return active project details.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create novel project.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const computedFolder =
    folderName.trim() ||
    title
      .trim()
      .replace(/[<>:"/\\|?*]/g, '_')
      .replace(/^\.+/, '') ||
    'new_novel';

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-sm shadow-md shadow-indigo-500/20">
              ✨
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">Initialize New Novel Project</h2>
              <p className="text-[11px] text-slate-400">
                Created inside <span className="font-mono text-indigo-400 font-semibold">{projectsDirName}/</span>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {errorMsg && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400 text-xs">
              {errorMsg}
            </div>
          )}

          {/* Novel Title */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">
              Novel Title <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. The Rising of the Shield Hero"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-xs"
            />
          </div>

          {/* Folder Name */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">
              Folder Name <span className="text-slate-500 font-normal">(Optional, auto-derived from title)</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={folderName}
                onChange={(e) => setFolderName(e.target.value)}
                placeholder="e.g. Shield_Hero"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
            <div className="mt-1 text-[11px] text-slate-500 flex items-center gap-1.5">
              <FolderPlus className="w-3.5 h-3.5 text-indigo-400" />
              <span>Target: <code className="text-indigo-300">{projectsDirName}/{computedFolder}</code></span>
            </div>
          </div>

          {/* Language Pair */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Source Language
              </label>
              <input
                type="text"
                value={sourceLanguage}
                onChange={(e) => setSourceLanguage(e.target.value)}
                placeholder="Japanese, Chinese, Korean, Auto"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Target Language
              </label>
              <input
                type="text"
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                placeholder="Thai, English..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
          </div>

          {/* Genre & Model */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Novel Genre
              </label>
              <select
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-indigo-500 text-xs cursor-pointer"
              >
                <option value="general">General Fantasy / Fiction</option>
                <option value="isekai">Isekai (Other World)</option>
                <option value="xianxia">Xianxia / Wuxia (Cultivation)</option>
                <option value="litrpg">LitRPG / Game System</option>
                <option value="romance">Villainess / Romance</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Primary Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 font-mono text-slate-200 focus:outline-none focus:border-indigo-500 text-xs"
                placeholder="gemini-3.5-flash-lite"
              />
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-md shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {isSubmitting ? 'Creating...' : 'Initialize Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
