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
  Loader2,
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
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150 font-sans">
      <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-xl w-full overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-[#3f3a36] flex items-center justify-between bg-[#2b2622]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-[3px] bg-[#383330] border border-[#3f3a36] flex items-center justify-center text-[#f7f5f0]">
              <Upload className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#f7f5f0] font-mono">
                Upload Raw Chapters
              </h2>
              <p className="text-[11px] text-[#857d75]">
                Target project: <span className="font-semibold text-[#b0a89f]">{activeProjectTitle || 'Project'}</span>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="p-1 rounded-[2px] text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#383330] transition-colors cursor-pointer disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleUpload} className="p-5 space-y-3.5 text-xs overflow-y-auto flex-1">
          {/* Status Alerts */}
          {errorMsg && (
            <div className="p-2.5 bg-[#382522] border border-[#cf6659]/40 rounded-[3px] text-[#e67b73] text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-2.5 bg-[#272f26] border border-[#7fa678]/40 rounded-[3px] text-[#a5c49f] text-xs flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Target Folder Selector */}
          <div className="space-y-1">
            <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5">
              <Folder className="w-3.5 h-3.5 text-[#857d75]" />
              Destination Folder in Project
            </label>
            <select
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              disabled={isUploading}
              className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] cursor-pointer disabled:opacity-50 font-mono"
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
              <div className="mt-2 space-y-1">
                <div className="flex items-center gap-1.5">
                  <FolderPlus className="w-3.5 h-3.5 text-[#d9a05b] shrink-0" />
                  <input
                    type="text"
                    placeholder="e.g. Villainess_05 or Vol_02"
                    value={customFolderName}
                    onChange={(e) => setCustomFolderName(e.target.value)}
                    disabled={isUploading}
                    autoFocus
                    className="flex-1 bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] font-mono"
                  />
                </div>
                <p className="text-[10px] text-[#857d75] pl-5 font-mono">
                  Path: <span>{effectiveFolderDisplay}/</span>
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
            className={`border border-dashed rounded-[4px] p-5 text-center cursor-pointer transition-colors flex flex-col items-center justify-center gap-2 ${
              isDragging
                ? 'border-[#f7f5f0] bg-[#383330]'
                : 'border-[#3f3a36] hover:border-[#857d75] bg-[#24201d]'
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
            <div className="w-8 h-8 rounded-[3px] bg-[#383330] border border-[#3f3a36] flex items-center justify-center text-[#f7f5f0]">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <p className="font-medium text-[#f7f5f0] text-xs">
                Drag & drop novel chapter files here, or{' '}
                <span className="underline underline-offset-2 text-[#b0a89f] hover:text-[#f7f5f0]">
                  browse files
                </span>
              </p>
              <p className="text-[11px] text-[#857d75] mt-0.5 font-mono">
                Accepts .txt and .md UTF-8 chapters
              </p>
            </div>
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between font-mono text-[11px]">
                <span className="font-semibold text-[#b0a89f] flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-[#857d75]" />
                  Files ({selectedFiles.length})
                </span>
                <button
                  type="button"
                  onClick={clearAllFiles}
                  disabled={isUploading}
                  className="text-[#cf6659] hover:text-[#e67b73] transition-colors cursor-pointer"
                >
                  Clear all
                </button>
              </div>

              <div className="max-h-36 overflow-y-auto space-y-1 pr-1 rounded-[3px] border border-[#3f3a36] bg-[#24201d] p-1.5">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between py-1 px-2 rounded-[2px] bg-[#2b2622] border border-[#3f3a36] text-[#f7f5f0] text-xs font-mono"
                  >
                    <div className="flex items-center gap-1.5 truncate pr-2">
                      <FileText className="w-3 h-3 text-[#857d75] shrink-0" />
                      <span className="truncate">{file.name}</span>
                      <span className="text-[10px] text-[#857d75] shrink-0">
                        ({formatFileSize(file.size)})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(idx)}
                      disabled={isUploading}
                      title="Remove file"
                      className="p-0.5 text-[#857d75] hover:text-[#cf6659] transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Overwrite Option */}
          <div className="pt-0.5">
            <label className="flex items-center gap-2 text-[#b0a89f] cursor-pointer select-none text-xs">
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
                disabled={isUploading}
                className="rounded-[2px] accent-[#f7f5f0] cursor-pointer"
              />
              <span>Overwrite existing files if already present</span>
            </label>
          </div>

          {/* Footer Actions */}
          <div className="pt-3 border-t border-[#3f3a36] flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-3.5 py-1.5 rounded-[3px] bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isUploading || selectedFiles.length === 0}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-[3px] bg-[#f7f5f0] hover:bg-[#e2ded6] text-[#2b2622] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-3.5 h-3.5" />
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
