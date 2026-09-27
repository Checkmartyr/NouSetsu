import React, { useState, useEffect } from 'react';
import {
  X,
  BookOpen,
  Download,
  Printer,
  Folder,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  Settings2,
} from 'lucide-react';
import { fetchProjectFolders, exportEbook } from '../services/dashboardApi';
import { EbookExportOptions } from '../types/dashboard';

interface ExportBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeProjectPath: string | null;
  activeProjectTitle?: string | null;
}

export const ExportBookModal: React.FC<ExportBookModalProps> = ({
  isOpen,
  onClose,
  activeProjectPath,
  activeProjectTitle,
}) => {
  const [format, setFormat] = useState<'epub' | 'pdf'>('epub');
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>('all');
  const [title, setTitle] = useState<string>('');
  const [author, setAuthor] = useState<string>('');
  const [includeBibleAppendix, setIncludeBibleAppendix] = useState<boolean>(true);
  const [softWrapThai, setSoftWrapThai] = useState<boolean>(true);
  const [includeImages, setIncludeImages] = useState<boolean>(true);

  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && activeProjectPath) {
      setTitle(activeProjectTitle || 'Novel');
      setAuthor('');
      setErrorMsg(null);
      setSuccessMsg(null);

      fetchProjectFolders(activeProjectPath).then((data) => {
        // Collect translated folders or folders with _th / _trans
        const validFolders = data.folders.filter(
          (f) => f.endsWith('_th') || f.endsWith('_trans') || f === 'translated_chapters'
        );
        setFolders(validFolders.length > 0 ? validFolders : data.folders);
        setSelectedFolder(data.default_folder || 'all');
      });
    }
  }, [isOpen, activeProjectPath, activeProjectTitle]);

  if (!isOpen) return null;

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectPath) {
      setErrorMsg('No active project selected.');
      return;
    }

    setIsExporting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const options: EbookExportOptions = {
        project_path: activeProjectPath,
        format: format,
        folder: selectedFolder === 'all' ? undefined : selectedFolder,
        title: title.trim() || undefined,
        author: author.trim() || undefined,
        include_bible_appendix: includeBibleAppendix,
        soft_wrap_thai: softWrapThai,
        include_images: includeImages,
      };

      const { blob, filename } = await exportEbook(options);

      // Trigger browser download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccessMsg(`Successfully generated and downloaded ${filename}!`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to export eBook');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="bg-[#1c1815] border border-[#3f3a36] rounded-[4px] shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-4 border-b border-[#3f3a36] flex items-center justify-between bg-[#24201d]">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-[#d9a05b]" />
            <h2 className="text-sm font-mono font-bold text-[#f7f5f0]">Export Novel eBook</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#857d75] hover:text-[#f7f5f0] transition-colors p-1 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Status Alerts */}
        {errorMsg && (
          <div className="mx-5 mt-3.5 p-2.5 bg-[#382522] border border-[#cf6659]/40 rounded-[3px] text-[#e67b73] text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mx-5 mt-3.5 p-2.5 bg-[#272f26] border border-[#7fa678]/40 rounded-[3px] text-[#a5c49f] text-xs flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleExport} className="p-5 space-y-4 text-xs overflow-y-auto flex-1">
          {/* Format Selector */}
          <div className="space-y-1.5">
            <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#857d75]" />
              Target Format
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <div
                onClick={() => setFormat('epub')}
                className={`p-3 rounded-[3px] border cursor-pointer transition-all flex flex-col gap-1 ${
                  format === 'epub'
                    ? 'bg-[#2b2622] border-[#d9a05b] text-[#f7f5f0]'
                    : 'bg-[#24201d] border-[#3f3a36] text-[#857d75] hover:border-[#524c46]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-xs flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-[#d9a05b]" />
                    EPUB3 Book
                  </span>
                  <span className="text-[10px] px-1 py-0.2 bg-[#d9a05b]/20 text-[#d9a05b] rounded-[2px] font-mono">
                    .epub
                  </span>
                </div>
                <p className="text-[11px] text-[#857d75]">
                  Standard e-reader package with metadata, TOC, cover, and reader styles.
                </p>
              </div>

              <div
                onClick={() => setFormat('pdf')}
                className={`p-3 rounded-[3px] border cursor-pointer transition-all flex flex-col gap-1 ${
                  format === 'pdf'
                    ? 'bg-[#2b2622] border-[#94a8c9] text-[#f7f5f0]'
                    : 'bg-[#24201d] border-[#3f3a36] text-[#857d75] hover:border-[#524c46]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-xs flex items-center gap-1.5">
                    <Printer className="w-3.5 h-3.5 text-[#94a8c9]" />
                    Printable HTML / PDF
                  </span>
                  <span className="text-[10px] px-1 py-0.2 bg-[#94a8c9]/20 text-[#94a8c9] rounded-[2px] font-mono">
                    .html
                  </span>
                </div>
                <p className="text-[11px] text-[#857d75]">
                  Print-ready layout with Sarabun typography, page breaks, and 1-click Ctrl+P printing.
                </p>
              </div>
            </div>
          </div>

          {/* Folder Selector */}
          <div className="space-y-1">
            <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5">
              <Folder className="w-3.5 h-3.5 text-[#857d75]" />
              Source Volume / Folder
            </label>
            <select
              value={selectedFolder}
              onChange={(e) => setSelectedFolder(e.target.value)}
              disabled={isExporting}
              className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] cursor-pointer disabled:opacity-50 font-mono"
            >
              <option value="all">Entire Novel (Default Translated Directory)</option>
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          {/* Book Title & Author */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[#b0a89f] font-mono text-[11px]">Book Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Novel Title"
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[#b0a89f] font-mono text-[11px]">Author Name</label>
              <input
                type="text"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="Author Name (Optional)"
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f]"
              />
            </div>
          </div>

          {/* Publication Toggles */}
          <div className="p-3 bg-[#24201d] border border-[#3f3a36] rounded-[3px] space-y-2.5">
            <span className="text-[#b0a89f] font-mono text-[11px] font-semibold flex items-center gap-1.5">
              <Settings2 className="w-3.5 h-3.5 text-[#d9a05b]" />
              Publication Options
            </span>

            <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer">
              <input
                type="checkbox"
                checked={softWrapThai}
                onChange={(e) => setSoftWrapThai(e.target.checked)}
                className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
              />
              <span>Thai zero-width space soft-wrapping (protects natural line breaks)</span>
            </label>

            <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer">
              <input
                type="checkbox"
                checked={includeBibleAppendix}
                onChange={(e) => setIncludeBibleAppendix(e.target.checked)}
                className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
              />
              <span>Include Novel Bible Appendix (Character Profiles & Glossary Terms)</span>
            </label>

            <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer">
              <input
                type="checkbox"
                checked={includeImages}
                onChange={(e) => setIncludeImages(e.target.checked)}
                className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
              />
              <span>Embed illustrations and cover image from assets/</span>
            </label>
          </div>

          {/* Action Footer */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isExporting}
              className="px-3.5 py-1.5 rounded-[3px] text-xs font-mono text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#2b2622] transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isExporting}
              className="px-4 py-1.5 rounded-[3px] text-xs font-mono font-medium bg-[#d9a05b] text-[#1c1815] hover:bg-[#e0ab6c] transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-sm"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Compiling Book...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Compile & Download</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
