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
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150 font-sans">
      <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-lg w-full overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-[#3f3a36] flex items-center justify-between bg-[#2b2622]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-[3px] bg-[#383330] border border-[#3f3a36] flex items-center justify-center text-xs text-[#d9a05b]">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#f7f5f0] font-mono">
                Initialize New Novel Project
              </h2>
              <p className="text-[11px] text-[#857d75]">
                Target directory: <span className="font-mono text-[#b0a89f]">{projectsDirName}/</span>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-[2px] text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#383330] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-3.5 text-xs">
          {errorMsg && (
            <div className="p-2.5 bg-[#382522] border border-[#cf6659]/40 rounded-[3px] text-[#e67b73] text-xs">
              {errorMsg}
            </div>
          )}

          {/* Novel Title */}
          <div>
            <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
              Novel Title <span className="text-[#cf6659]">*</span>
            </label>
            <input
              type="text"
              required
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. The Rising of the Shield Hero"
              className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-[#f7f5f0] placeholder-[#857d75] focus:outline-none focus:border-[#b0a89f] text-xs"
            />
          </div>

          {/* Folder Name */}
          <div>
            <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
              Folder Name <span className="text-[#857d75] font-normal">(Optional, auto-derived)</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={folderName}
                onChange={(e) => setFolderName(e.target.value)}
                placeholder="e.g. Shield_Hero"
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 font-mono text-[#f7f5f0] placeholder-[#857d75] focus:outline-none focus:border-[#b0a89f] text-xs"
              />
            </div>
            <div className="mt-1 text-[11px] text-[#857d75] font-mono flex items-center gap-1.5">
              <FolderPlus className="w-3.5 h-3.5 text-[#857d75]" />
              <span>Target: <code>{projectsDirName}/{computedFolder}</code></span>
            </div>
          </div>

          {/* Language Pair */}
          <div className="grid grid-cols-2 gap-3 pt-0.5">
            <div>
              <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
                Source Language
              </label>
              <input
                type="text"
                value={sourceLanguage}
                onChange={(e) => setSourceLanguage(e.target.value)}
                placeholder="Japanese, Chinese, Korean, Auto"
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] text-xs font-mono"
              />
            </div>

            <div>
              <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
                Target Language
              </label>
              <input
                type="text"
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                placeholder="Thai, English..."
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] text-xs font-mono"
              />
            </div>
          </div>

          {/* Genre & Model */}
          <div className="grid grid-cols-2 gap-3 pt-0.5">
            <div>
              <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
                Novel Genre
              </label>
              <select
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] text-xs cursor-pointer font-mono"
              >
                <option value="general">General Fantasy / Fiction</option>
                <option value="isekai">Isekai (Other World)</option>
                <option value="xianxia">Xianxia / Wuxia (Cultivation)</option>
                <option value="litrpg">LitRPG / Game System</option>
                <option value="romance">Villainess / Romance</option>
              </select>
            </div>

            <div>
              <label className="block text-[#b0a89f] font-mono text-[11px] mb-1">
                Primary Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 font-mono text-[#f7f5f0] focus:outline-none focus:border-[#b0a89f] text-xs"
                placeholder="gemini-3.5-flash-lite"
              />
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#3f3a36]">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3.5 py-1.5 bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] rounded-[3px] border border-[#3f3a36] text-xs font-medium cursor-pointer transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#f7f5f0] hover:bg-[#e2ded6] text-[#2b2622] rounded-[3px] text-xs font-semibold cursor-pointer transition-colors disabled:opacity-50"
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
