import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Upload,
  Folder,
  FolderPlus,
  FileText,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { fetchProjectFolders, uploadChapters } from '../services/dashboardApi';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeProjectPath: string | null;
  activeProjectTitle?: string | null;
  onUploadSuccess: (result: { folder: string; uploadedCount: number }) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  activeProjectPath,
  activeProjectTitle,
  onUploadSuccess,
}) => {
  const [folders, setFolders] = useState<string[]>(['raw_chapters']);
  const [defaultFolder, setDefaultFolder] = useState<string>('raw_chapters');
  const [selectedFolder, setSelectedFolder] = useState<string>('raw_chapters');
  const [customFolderName, setCustomFolderName] = useState<string>('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [overwrite, setOverwrite] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load project folders when modal opens
  useEffect(() => {
    if (isOpen && activeProjectPath) {
      fetchProjectFolders(activeProjectPath).then((data) => {
        setFolders(data.folders);
        setDefaultFolder(data.default_folder);
        setSelectedFolder(data.default_folder);
      });
      setSelectedFiles([]);
      setCustomFolderName('');
      setErrorMsg(null);
      setSuccessMsg(null);
    }
  }, [isOpen, activeProjectPath]);

  if (!isOpen) return null;

  const handleFilesChosen = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const allowed = Array.from(fileList).filter((f) => {
      const name = f.name.toLowerCase();
      return name.endsWith('.txt') || name.endsWith('.md') || name.endsWith('.text');
    });

    if (allowed.length === 0) {
      setErrorMsg('Please select text files (.txt, .md).');
      return;
    }

    setErrorMsg(null);
    setSelectedFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const newFiles = allowed.filter((f) => !existingNames.has(f.name));
      return [...prev, ...newFiles];
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFilesChosen(e.dataTransfer.files);
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const clearAllFiles = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectPath) {
      setErrorMsg('No active project selected.');
      return;
    }

    if (selectedFiles.length === 0) {
      setErrorMsg('Please select at least one chapter file to upload.');
      return;
    }

    const targetFolder =
      selectedFolder === '__new__' ? customFolderName.trim() : selectedFolder;

    if (selectedFolder === '__new__' && !targetFolder) {
      setErrorMsg('Please provide a name for the new folder.');
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      // Read all files as text in parallel
      const filePayloads = await Promise.all(
        selectedFiles.map(async (file) => ({
          name: file.name,
          content: await file.text(),
        }))
      );

      const result = await uploadChapters({
        files: filePayloads,
        projectPath: activeProjectPath,
        folder: targetFolder,
        overwrite,
      });

      if (result.success) {
        setSuccessMsg(result.message);
        onUploadSuccess({
          folder: result.folder,
          uploadedCount: result.total_uploaded,
        });

        // Close modal after brief confirmation
        setTimeout(() => {
          onClose();
        }, 1200);
      } else {
        setErrorMsg('Upload failed. Please check server logs.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to upload chapter files.');
    } finally {
      setIsUploading(false);
    }
  };

  const effectiveFolderDisplay =
    selectedFolder === '__new__'
      ? customFolderName.trim() || 'new_folder'
      : selectedFolder;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-500/20 text-white">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">Upload Raw Chapters</h2>
              <p className="text-[11px] text-slate-400">
                Add chapter files for translation to{' '}
                <span className="font-semibold text-indigo-300">
                  {activeProjectTitle || 'Project'}
                </span>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleUpload} className="p-6 space-y-4 text-xs overflow-y-auto flex-1">
          {/* Status Alerts */}
          {errorMsg && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Target Folder Selector */}
          <div className="space-y-1.5">
            <label className="text-slate-300 font-medium flex items-center gap-1.5">
              <Folder className="w-3.5 h-3.5 text-indigo-400" />
              Destination Folder in Project
            </label>
            <select
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              disabled={isUploading}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 cursor-pointer disabled:opacity-50"
            >
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f} {f === defaultFolder ? '(Default Raw Directory)' : '(Volume Subfolder)'}
                </option>
              ))}
              <option value="__new__">+ Create New Subfolder / Volume...</option>
            </select>

            {/* Custom Folder Input */}
            {selectedFolder === '__new__' && (
              <div className="mt-2 space-y-1 animate-in fade-in duration-150">
                <div className="flex items-center gap-2">
                  <FolderPlus className="w-4 h-4 text-purple-400 shrink-0" />
                  <input
                    type="text"
                    placeholder="e.g. Villainess_05 or Vol_02"
                    value={customFolderName}
                    onChange={(e) => setCustomFolderName(e.target.value)}
                    disabled={isUploading}
                    autoFocus
                    className="flex-1 bg-slate-950 border border-purple-500/50 rounded-lg px-3 py-1.5 text-slate-100 text-xs focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400/40"
                  />
                </div>
                <p className="text-[11px] text-slate-500 pl-6">
                  Will be created at: <span className="font-mono text-purple-300">{effectiveFolderDisplay}/</span>
                </p>
              </div>
            )}
          </div>

          {/* Drag & Drop File Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-2 ${
              isDragging
                ? 'border-indigo-500 bg-indigo-500/10 scale-[0.99]'
                : 'border-slate-800 hover:border-slate-700 bg-slate-950/60 hover:bg-slate-950'
            } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.text"
              onChange={(e) => handleFilesChosen(e.target.files)}
              className="hidden"
            />
            <div className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-indigo-400 shadow-inner">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <p className="font-medium text-slate-200">
                Drag & drop novel chapter files here, or{' '}
                <span className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300">
                  browse files
                </span>
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Accepts <span className="font-mono text-slate-400">.txt</span> and{' '}
                <span className="font-mono text-slate-400">.md</span> UTF-8 chapters
              </p>
            </div>
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-indigo-400" />
                  Files to Upload ({selectedFiles.length})
                </span>
                <button
                  type="button"
                  onClick={clearAllFiles}
                  disabled={isUploading}
                  className="text-[11px] text-rose-400 hover:text-rose-300 transition-colors cursor-pointer"
                >
                  Clear all
                </button>
              </div>

              <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1 rounded-lg border border-slate-800/80 bg-slate-950/40 p-2">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between py-1 px-2.5 rounded-lg bg-slate-900 border border-slate-800/60 text-slate-300 text-xs"
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      <FileText className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                      <span className="truncate font-mono">{file.name}</span>
                      <span className="text-[10px] text-slate-500 shrink-0">
                        ({formatFileSize(file.size)})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(idx)}
                      disabled={isUploading}
                      title="Remove file"
                      className="p-1 text-slate-500 hover:text-rose-400 transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Overwrite Option */}
          <div className="pt-1">
            <label className="flex items-center gap-2 text-slate-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
                disabled={isUploading}
                className="rounded accent-indigo-600 cursor-pointer"
              />
              <span className="text-xs">
                Overwrite existing files if already present in target folder
              </span>
            </label>
          </div>

          {/* Footer Actions */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isUploading || selectedFiles.length === 0}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 text-white" />
                  Upload {selectedFiles.length > 0 ? `${selectedFiles.length} Chapters` : 'Files'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
