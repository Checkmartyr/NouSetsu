import React, { useState, useEffect, useCallback } from 'react';
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
  Type,
  Minus,
  Plus,
  ChevronLeft,
  ChevronRight,
  List,
  FileText,
  RefreshCw,
  FileCode,
  Image as ImageIcon,
} from 'lucide-react';
import { fetchProjectFolders, exportEbook, previewEbook } from '../services/dashboardApi';
import { EbookExportOptions, EbookPreviewResult, TranslatedFolderItem } from '../types/dashboard';

interface ExportBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeProjectPath: string | null;
  activeProjectTitle?: string | null;
  initialFolder?: string | null;
}

const FONT_OPTIONS = [
  { id: 'Sarabun', name: 'Sarabun (สารบรรณ)', category: 'Official / Publication Standard', css: "'Sarabun', sans-serif" },
  { id: 'Prompt', name: 'Prompt (พร้อม)', category: 'Modern Geometric Sans', css: "'Prompt', sans-serif" },
  { id: 'Kanit', name: 'Kanit (คณิต)', category: 'Contemporary / Expressive', css: "'Kanit', sans-serif" },
  { id: 'Noto Serif Thai', name: 'Noto Serif Thai', category: 'Classic Literary Serif', css: "'Noto Serif Thai', serif" },
  { id: 'Chakra Petch', name: 'Chakra Petch', category: 'Futuristic / Angular', css: "'Chakra Petch', sans-serif" },
];

export const ExportBookModal: React.FC<ExportBookModalProps> = ({
  isOpen,
  onClose,
  activeProjectPath,
  activeProjectTitle,
  initialFolder,
}) => {
  const [format, setFormat] = useState<'pdf' | 'epub' | 'html'>('pdf');
  const [folders, setFolders] = useState<string[]>([]);
  const [translatedFolders, setTranslatedFolders] = useState<TranslatedFolderItem[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>('all');
  const [title, setTitle] = useState<string>('');
  const [author, setAuthor] = useState<string>('');
  const [includeBibleAppendix, setIncludeBibleAppendix] = useState<boolean>(true);
  const [softWrapThai, setSoftWrapThai] = useState<boolean>(true);
  const [includeImages, setIncludeImages] = useState<boolean>(true);

  // Typography controls
  const [fontFamily, setFontFamily] = useState<string>('Sarabun');
  const [fontSize, setFontSize] = useState<number>(16);
  const [lineHeight, setLineHeight] = useState<number>(1.8);

  // Preview state
  const [previewTab, setPreviewTab] = useState<'toc' | 'chapter'>('chapter');
  const [previewIndex, setPreviewIndex] = useState<number>(1);
  const [previewData, setPreviewData] = useState<EbookPreviewResult | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);

  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadPreview = useCallback(async (targetIndex: number) => {
    if (!activeProjectPath) return;
    setIsLoadingPreview(true);
    try {
      const opts: EbookExportOptions = {
        project_path: activeProjectPath,
        folder: selectedFolder === 'all' ? undefined : selectedFolder,
        title: title.trim() || undefined,
        author: author.trim() || undefined,
        font_family: fontFamily,
        font_size: fontSize,
        line_height: lineHeight,
        apply_thai_word_wrap: softWrapThai,
        include_bible_appendix: includeBibleAppendix,
      };
      const res = await previewEbook(opts, targetIndex);
      setPreviewData(res);
      setPreviewIndex(res.sample_chapter_index);
    } catch (err: any) {
      console.warn('Could not load eBook preview:', err);
    } finally {
      setIsLoadingPreview(false);
    }
  }, [activeProjectPath, selectedFolder, title, author, fontFamily, fontSize, lineHeight, softWrapThai, includeBibleAppendix]);

  useEffect(() => {
    if (isOpen && activeProjectPath) {
      setTitle(activeProjectTitle || 'Novel');
      setAuthor('');
      setErrorMsg(null);
      setSuccessMsg(null);

      fetchProjectFolders(activeProjectPath).then((data) => {
        setFolders(data.folders || []);
        const tFolders = data.translated_folders || [];
        setTranslatedFolders(tFolders);

        // Determine default export folder:
        // 1. If initialFolder passed from StudioView, resolve matching translated folder
        if (initialFolder && initialFolder !== 'all') {
          const match = tFolders.find(
            (tf) => tf.folder === initialFolder || tf.folder.startsWith(`${initialFolder}_`)
          );
          if (match) {
            setSelectedFolder(match.folder);
            return;
          }
          setSelectedFolder(initialFolder);
          return;
        }

        // 2. Use backend's default_translated_folder
        if (data.default_translated_folder) {
          setSelectedFolder(data.default_translated_folder);
          return;
        }

        // 3. Pick non-empty translated folder or default
        const nonNull = tFolders.find((tf) => tf.chapter_count > 0);
        if (nonNull) {
          setSelectedFolder(nonNull.folder);
        } else {
          setSelectedFolder(data.default_folder || 'all');
        }
      });
    }
  }, [isOpen, activeProjectPath, activeProjectTitle, initialFolder]);

  useEffect(() => {
    if (isOpen && activeProjectPath) {
      loadPreview(previewIndex);
    }
  }, [isOpen, activeProjectPath, selectedFolder, loadPreview]);

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
        apply_thai_word_wrap: softWrapThai,
        soft_wrap_thai: softWrapThai,
        include_images: includeImages,
        font_family: fontFamily,
        font_size: fontSize,
        line_height: lineHeight,
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

  const currentFontObj = FONT_OPTIONS.find((f) => f.id === fontFamily) || FONT_OPTIONS[0];

  const handleSelectChapter = (idx: number) => {
    setPreviewIndex(idx);
    setPreviewTab('chapter');
    loadPreview(idx);
  };

  const handlePrevChapter = () => {
    if (previewIndex > 1) {
      handleSelectChapter(previewIndex - 1);
    }
  };

  const handleNextChapter = () => {
    if (previewData && previewIndex < previewData.total_chapters) {
      handleSelectChapter(previewIndex + 1);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-3 md:p-6">
      {/* Load Google Fonts for Live Preview */}
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Chakra+Petch:ital,wght@0,400;0,600;1,400&family=Kanit:ital,wght@0,300;0,400;0,600;1,400&family=Noto+Serif+Thai:wght@400;600&family=Prompt:ital,wght@0,300;0,400;0,600;1,400&family=Sarabun:ital,wght@0,300;0,400;0,600;1,400&display=swap"
      />

      <div className="bg-[#1c1815] border border-[#3f3a36] rounded-[6px] shadow-2xl w-full max-w-6xl h-[92vh] max-h-[920px] overflow-hidden flex flex-col">
        {/* Modal Top Bar */}
        <div className="px-5 py-3 border-b border-[#3f3a36] flex items-center justify-between bg-[#24201d] shrink-0">
          <div className="flex items-center gap-2.5">
            <BookOpen className="w-4 h-4 text-[#d9a05b]" />
            <h2 className="text-sm font-mono font-bold text-[#f7f5f0]">eBook Export &amp; Live Publication Studio</h2>
            <span className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-mono bg-[#322c27] text-[#b0a89f] rounded-[2px] border border-[#4a423b]">
              PyMuPDF + EPUB3
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-[#857d75] hover:text-[#f7f5f0] transition-colors p-1 cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Status Alerts */}
        {errorMsg && (
          <div className="mx-5 mt-2.5 p-2 bg-[#382522] border border-[#cf6659]/40 rounded-[3px] text-[#e67b73] text-xs flex items-start gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="flex-1">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="cursor-pointer text-[#857d75] hover:text-white">✕</button>
          </div>
        )}

        {successMsg && (
          <div className="mx-5 mt-2.5 p-2 bg-[#272f26] border border-[#7fa678]/40 rounded-[3px] text-[#a5c49f] text-xs flex items-start gap-2 shrink-0">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="flex-1">{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="cursor-pointer text-[#857d75] hover:text-white">✕</button>
          </div>
        )}

        {/* Dual Panel Body */}
        <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
          {/* ========================================================================= */}
          {/* LEFT PANEL: Export Configuration                                          */}
          {/* ========================================================================= */}
          <form
            onSubmit={handleExport}
            className="w-full md:w-[380px] border-r border-[#3f3a36] bg-[#1a1714] p-4 flex flex-col gap-3 text-xs overflow-y-auto shrink-0"
          >
            {/* Target Format Selector */}
            <div className="space-y-1.5">
              <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5 font-medium">
                <Layers className="w-3.5 h-3.5 text-[#857d75]" />
                Export Format
              </label>
              <div className="grid grid-cols-3 gap-2">
                <div
                  onClick={() => setFormat('pdf')}
                  className={`p-2.5 rounded-[4px] border cursor-pointer transition-all flex flex-col gap-0.5 ${
                    format === 'pdf'
                      ? 'bg-[#2b2622] border-[#d9a05b] text-[#f7f5f0] shadow-sm'
                      : 'bg-[#24201d] border-[#3f3a36] text-[#857d75] hover:border-[#524c46]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs flex items-center gap-1">
                      <Printer className="w-3.5 h-3.5 text-[#d9a05b]" />
                      PDF Book
                    </span>
                  </div>
                  <span className="text-[10px] text-[#857d75] font-mono">.pdf (Native)</span>
                </div>

                <div
                  onClick={() => setFormat('epub')}
                  className={`p-2.5 rounded-[4px] border cursor-pointer transition-all flex flex-col gap-0.5 ${
                    format === 'epub'
                      ? 'bg-[#2b2622] border-[#d9a05b] text-[#f7f5f0] shadow-sm'
                      : 'bg-[#24201d] border-[#3f3a36] text-[#857d75] hover:border-[#524c46]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs flex items-center gap-1">
                      <BookOpen className="w-3.5 h-3.5 text-[#94a8c9]" />
                      EPUB3
                    </span>
                  </div>
                  <span className="text-[10px] text-[#857d75] font-mono">.epub (E-Reader)</span>
                </div>

                <div
                  onClick={() => setFormat('html')}
                  className={`p-2.5 rounded-[4px] border cursor-pointer transition-all flex flex-col gap-0.5 ${
                    format === 'html'
                      ? 'bg-[#2b2622] border-[#d9a05b] text-[#f7f5f0] shadow-sm'
                      : 'bg-[#24201d] border-[#3f3a36] text-[#857d75] hover:border-[#524c46]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs flex items-center gap-1">
                      <FileCode className="w-3.5 h-3.5 text-[#7fa678]" />
                      Web HTML
                    </span>
                  </div>
                  <span className="text-[10px] text-[#857d75] font-mono">.html (Print)</span>
                </div>
              </div>
            </div>

            {/* Folder / Volume Selector */}
            <div className="space-y-1">
              <label className="text-[#b0a89f] font-mono text-[11px] flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Folder className="w-3.5 h-3.5 text-[#857d75]" />
                  Volume / Source Folder
                </span>
                <button
                  type="button"
                  onClick={() => loadPreview(previewIndex)}
                  className="text-[#857d75] hover:text-[#d9a05b] flex items-center gap-1 cursor-pointer"
                  title="Refresh chapter list"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Sync</span>
                </button>
              </label>
              <select
                value={selectedFolder}
                onChange={(e) => setSelectedFolder(e.target.value)}
                disabled={isExporting}
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] cursor-pointer disabled:opacity-50 font-mono"
              >
                {translatedFolders.length > 0 ? (
                  translatedFolders.map((tf) => (
                    <option key={tf.folder} value={tf.folder}>
                      {tf.name} ({tf.chapter_count} chapters){tf.is_default ? ' ★ Default' : ''}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="all">Entire Novel (translated_chapters/)</option>
                    {folders.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </div>

            {/* Title & Author */}
            <div className="space-y-2">
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

            {/* Publication Options */}
            <div className="p-3 bg-[#24201d] border border-[#3f3a36] rounded-[4px] space-y-2">
              <span className="text-[#b0a89f] font-mono text-[11px] font-semibold flex items-center gap-1.5">
                <Settings2 className="w-3.5 h-3.5 text-[#d9a05b]" />
                Publication Directives
              </span>

              <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer select-none text-[11px]">
                <input
                  type="checkbox"
                  checked={softWrapThai}
                  onChange={(e) => setSoftWrapThai(e.target.checked)}
                  className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
                />
                <span>Thai zero-width space wrap (PyThaiNLP ZWSP)</span>
              </label>

              <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer select-none text-[11px]">
                <input
                  type="checkbox"
                  checked={includeBibleAppendix}
                  onChange={(e) => setIncludeBibleAppendix(e.target.checked)}
                  className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
                />
                <span>Novel Bible Appendix (Dossiers &amp; Glossary)</span>
              </label>

              <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer select-none text-[11px]">
                <input
                  type="checkbox"
                  checked={includeImages}
                  onChange={(e) => setIncludeImages(e.target.checked)}
                  className="rounded-[2px] accent-[#d9a05b] cursor-pointer"
                />
                <span>Embed illustrations and cover art from assets/</span>
              </label>
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Action Buttons */}
            <div className="pt-2 flex items-center justify-end gap-2 border-t border-[#3f3a36]">
              <button
                type="button"
                onClick={onClose}
                disabled={isExporting}
                className="px-3 py-1.5 rounded-[3px] text-xs font-mono text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#2b2622] transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={isExporting}
                className="px-4 py-2 rounded-[3px] text-xs font-mono font-bold bg-[#d9a05b] text-[#1c1815] hover:bg-[#e0ab6c] transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-md"
              >
                {isExporting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Compiling {format.toUpperCase()}...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Download {format.toUpperCase()}</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* ========================================================================= */}
          {/* RIGHT PANEL: Live Interactive Preview & Typography Toolbar                */}
          {/* ========================================================================= */}
          <div className="flex-1 flex flex-col bg-[#161311] min-w-0 overflow-hidden">
            {/* Typography & Tab Control Toolbar */}
            <div className="px-4 py-2.5 bg-[#201c19] border-b border-[#3f3a36] flex flex-wrap items-center justify-between gap-3 shrink-0">
              {/* Dual Tab Switcher */}
              <div className="flex items-center bg-[#181513] p-0.5 rounded-[4px] border border-[#36302a]">
                <button
                  type="button"
                  onClick={() => setPreviewTab('chapter')}
                  className={`px-3 py-1 rounded-[3px] font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${
                    previewTab === 'chapter'
                      ? 'bg-[#2b2622] text-[#d9a05b] font-bold shadow-xs'
                      : 'text-[#857d75] hover:text-[#dad2c1]'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Chapter Reader</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPreviewTab('toc')}
                  className={`px-3 py-1 rounded-[3px] font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${
                    previewTab === 'toc'
                      ? 'bg-[#2b2622] text-[#d9a05b] font-bold shadow-xs'
                      : 'text-[#857d75] hover:text-[#dad2c1]'
                  }`}
                >
                  <List className="w-3.5 h-3.5" />
                  <span>Table of Contents ({previewData?.total_chapters || 0})</span>
                </button>
              </div>

              {/* Typography Controls */}
              <div className="flex items-center gap-2.5 flex-wrap">
                {/* Font Family Selector */}
                <div className="flex items-center gap-1.5 bg-[#181513] px-2 py-1 rounded-[4px] border border-[#36302a]">
                  <Type className="w-3.5 h-3.5 text-[#d9a05b]" />
                  <select
                    value={fontFamily}
                    onChange={(e) => setFontFamily(e.target.value)}
                    className="bg-transparent text-[#f7f5f0] text-xs font-mono focus:outline-none cursor-pointer"
                  >
                    {FONT_OPTIONS.map((f) => (
                      <option key={f.id} value={f.id} className="bg-[#24201d] text-[#f7f5f0]">
                        {f.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Font Size Adjuster */}
                <div className="flex items-center bg-[#181513] rounded-[4px] border border-[#36302a] overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setFontSize((prev) => Math.max(12, prev - 1))}
                    disabled={fontSize <= 12}
                    className="px-2 py-1 text-[#b0a89f] hover:text-[#f7f5f0] hover:bg-[#2b2622] disabled:opacity-30 cursor-pointer"
                    title="Decrease font size"
                  >
                    <Minus className="w-3 h-3" />
                  </button>
                  <span className="px-2 py-0.5 text-xs font-mono text-[#d9a05b] min-w-[42px] text-center font-bold">
                    {fontSize}px
                  </span>
                  <button
                    type="button"
                    onClick={() => setFontSize((prev) => Math.min(26, prev + 1))}
                    disabled={fontSize >= 26}
                    className="px-2 py-1 text-[#b0a89f] hover:text-[#f7f5f0] hover:bg-[#2b2622] disabled:opacity-30 cursor-pointer"
                    title="Increase font size"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>

                {/* Line Height Selector */}
                <div className="flex items-center bg-[#181513] rounded-[4px] border border-[#36302a] p-0.5">
                  {[
                    { val: 1.5, label: '1.5x' },
                    { val: 1.8, label: '1.8x' },
                    { val: 2.0, label: '2.0x' },
                  ].map((lh) => (
                    <button
                      key={lh.val}
                      type="button"
                      onClick={() => setLineHeight(lh.val)}
                      className={`px-2 py-0.5 rounded-[2px] text-[11px] font-mono cursor-pointer transition-colors ${
                        lineHeight === lh.val
                          ? 'bg-[#2b2622] text-[#d9a05b] font-bold'
                          : 'text-[#857d75] hover:text-[#dad2c1]'
                      }`}
                    >
                      {lh.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Preview Viewport */}
            <div className="flex-1 relative overflow-y-auto p-4 md:p-8 flex justify-center bg-[#120f0d]">
              {isLoadingPreview && (
                <div className="absolute inset-0 z-20 bg-black/40 backdrop-blur-xs flex items-center justify-center">
                  <div className="bg-[#24201d] border border-[#3f3a36] px-4 py-2.5 rounded-[4px] flex items-center gap-2 text-xs font-mono text-[#f7f5f0]">
                    <Loader2 className="w-4 h-4 animate-spin text-[#d9a05b]" />
                    <span>Rendering publication preview...</span>
                  </div>
                </div>
              )}

              {/* TAB 1: Table of Contents */}
              {previewTab === 'toc' && (
                <div className="w-full max-w-2xl bg-[#1c1815] border border-[#36302a] rounded-[6px] p-6 shadow-xl space-y-4">
                  <div className="flex items-start justify-between border-b border-[#36302a] pb-4">
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-[#f7f5f0] font-mono">{previewData?.title || title}</h3>
                      <p className="text-xs text-[#857d75]">
                        {previewData?.author ? `By ${previewData.author} · ` : ''}
                        {previewData?.total_chapters || 0} Chapters · {previewData?.total_words?.toLocaleString() || 0} Words
                      </p>
                    </div>
                    {previewData?.has_cover && previewData.cover_base64 && (
                      <img
                        src={previewData.cover_base64}
                        alt="Book Cover"
                        className="w-14 h-20 object-cover rounded-[3px] border border-[#4a423b] shadow-md"
                      />
                    )}
                  </div>

                  <div className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1">
                    {previewData?.toc && previewData.toc.length > 0 ? (
                      previewData.toc.map((chap) => (
                        <div
                          key={chap.index}
                          onClick={() => handleSelectChapter(chap.index)}
                          className={`p-2.5 rounded-[4px] border cursor-pointer transition-all flex items-center justify-between ${
                            previewIndex === chap.index
                              ? 'bg-[#2b2622] border-[#d9a05b] text-[#f7f5f0]'
                              : 'bg-[#201c19] border-[#36302a] text-[#dad2c1] hover:border-[#524c46]'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="font-mono text-xs text-[#857d75] w-7">#{chap.index}</span>
                            <span className="font-medium text-xs text-[#f7f5f0]">{chap.title}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {chap.has_images && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-[2px] bg-[#36302a] text-[#b0a89f] flex items-center gap-1 font-mono">
                                <ImageIcon className="w-3 h-3 text-[#d9a05b]" />
                                img
                              </span>
                            )}
                            <span className="text-[11px] font-mono text-[#857d75]">{chap.word_count.toLocaleString()} words</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="p-8 text-center text-xs text-[#857d75]">
                        No translated chapters discovered in this volume.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: Chapter Prose Reader */}
              {previewTab === 'chapter' && (
                <div className="w-full max-w-3xl flex flex-col gap-4">
                  {/* Chapter Navigation Bar */}
                  <div className="bg-[#1c1815] border border-[#36302a] rounded-[4px] px-4 py-2 flex items-center justify-between shadow-md">
                    <button
                      type="button"
                      onClick={handlePrevChapter}
                      disabled={previewIndex <= 1 || isLoadingPreview}
                      className="flex items-center gap-1 text-xs font-mono text-[#b0a89f] hover:text-[#d9a05b] disabled:opacity-30 cursor-pointer transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      <span>Prev Chapter</span>
                    </button>

                    <div className="text-center font-mono text-xs text-[#f7f5f0] font-semibold">
                      <span>Chapter {previewIndex} of {previewData?.total_chapters || 1}</span>
                      <span className="block text-[11px] font-normal text-[#857d75] truncate max-w-xs sm:max-w-md">
                        {previewData?.sample_chapter_title || `Chapter ${previewIndex}`}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={handleNextChapter}
                      disabled={!previewData || previewIndex >= previewData.total_chapters || isLoadingPreview}
                      className="flex items-center gap-1 text-xs font-mono text-[#b0a89f] hover:text-[#d9a05b] disabled:opacity-30 cursor-pointer transition-colors"
                    >
                      <span>Next Chapter</span>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Publication Paper Container */}
                  <div className="bg-[#fcfbf9] text-[#1a1a1a] rounded-[4px] border border-[#e5e0d8] shadow-2xl p-6 md:p-12 transition-all">
                    {/* Chapter Header */}
                    <h1
                      className="font-bold text-center mb-6 pb-3 border-b border-[#e5e0d8] text-[#2b2622]"
                      style={{
                        fontFamily: currentFontObj.css,
                        fontSize: `${Math.round(fontSize * 1.35)}px`,
                        lineHeight: 1.3,
                      }}
                    >
                      {previewData?.sample_chapter_title || `Chapter ${previewIndex}`}
                    </h1>

                    {/* Prose Body */}
                    <div
                      className="ebook-preview-prose text-justify"
                      style={{
                        fontFamily: currentFontObj.css,
                        fontSize: `${fontSize}px`,
                        lineHeight: lineHeight,
                      }}
                      dangerouslySetInnerHTML={{
                        __html: previewData?.sample_chapter_html || '<p>Loading preview...</p>',
                      }}
                    />

                    {/* Bottom Page Number Simulation */}
                    <div className="mt-12 pt-4 border-t border-[#e5e0d8] text-center font-mono text-[10px] text-[#857d75]">
                      - Page {previewIndex} -
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
