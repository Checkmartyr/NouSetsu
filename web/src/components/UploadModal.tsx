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
  Globe,
  Zap,
  CheckSquare,
  Square,
  Sliders,
  BookOpen,
  Image as ImageIcon,
} from 'lucide-react';
import {
  fetchProjectFolders,
  uploadChapters,
  checkScraperAvailability,
  inspectScraperUrl,
  startScraperExtract,
  fetchScraperStatus,
  inspectEbook,
  importEbook,
} from '../services/dashboardApi';
import {
  ScraperInspectResult,
  ScraperStatusResult,
  EbookInspectResult,
} from '../types/dashboard';

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
  // Navigation tab
  const [activeTab, setActiveTab] = useState<'local' | 'url' | 'ebook'>('local');

  // Shared folder selection state
  const [folders, setFolders] = useState<string[]>(['raw_chapters']);
  const [defaultFolder, setDefaultFolder] = useState<string>('raw_chapters');
  const [selectedFolder, setSelectedFolder] = useState<string>('raw_chapters');
  const [customFolderName, setCustomFolderName] = useState<string>('');
  const [overwrite, setOverwrite] = useState(false);

  // Local files state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL Scraper state
  const [scraperUrl, setScraperUrl] = useState<string>('');
  const [scraperAvailable, setScraperAvailable] = useState<boolean | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectResult, setInspectResult] = useState<ScraperInspectResult | null>(null);
  const [selectionMode, setSelectionMode] = useState<'all' | 'range' | 'custom'>('all');
  const [rangeStart, setRangeStart] = useState<number>(1);
  const [rangeEnd, setRangeEnd] = useState<number>(10);
  const [selectedChapterIndices, setSelectedChapterIndices] = useState<Set<number>>(new Set());
  const [concurrency, setConcurrency] = useState<number>(3);
  const [includeFrontmatter, setIncludeFrontmatter] = useState<boolean>(false);
  const [isScraping, setIsScraping] = useState(false);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatusResult | null>(null);

  // eBook (EPUB/PDF) state
  const [ebookFile, setEbookFile] = useState<File | null>(null);
  const [isInspectingEbook, setIsInspectingEbook] = useState(false);
  const [ebookInspectResult, setEbookInspectResult] = useState<EbookInspectResult | null>(null);
  const [ebookExtractImages, setEbookExtractImages] = useState<boolean>(true);
  const [ebookSelectionMode, setEbookSelectionMode] = useState<'all' | 'range' | 'custom'>('all');
  const [ebookRangeStart, setEbookRangeStart] = useState<number>(1);
  const [ebookRangeEnd, setEbookRangeEnd] = useState<number>(10);
  const [selectedEbookIndices, setSelectedEbookIndices] = useState<Set<number>>(new Set());
  const [isImportingEbook, setIsImportingEbook] = useState(false);
  const ebookFileInputRef = useRef<HTMLInputElement>(null);

  // Feedback alerts
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load project folders & check scraper availability on open
  useEffect(() => {
    if (isOpen && activeProjectPath) {
      fetchProjectFolders(activeProjectPath).then((data) => {
        setFolders(data.folders);
        setDefaultFolder(data.default_folder);
        setSelectedFolder(data.default_folder);
      });
      checkScraperAvailability().then((res) => {
        setScraperAvailable(res.available);
      });
      setSelectedFiles([]);
      setCustomFolderName('');
      setInspectResult(null);
      setScraperStatus(null);
      setEbookFile(null);
      setEbookInspectResult(null);
      setIsInspectingEbook(false);
      setIsImportingEbook(false);
      setErrorMsg(null);
      setSuccessMsg(null);
    }
  }, [isOpen, activeProjectPath]);

  if (!isOpen) return null;

  // --------------------------------------------------------------------------
  // Local File Handlers
  // --------------------------------------------------------------------------

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

  const handleUploadLocal = async (e: React.FormEvent) => {
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

  // --------------------------------------------------------------------------
  // Scraper URL Handlers
  // --------------------------------------------------------------------------

  const handleInspectUrl = async () => {
    const trimmed = scraperUrl.trim();
    if (!trimmed) {
      setErrorMsg('Please enter a webnovel URL (e.g. from Syosetu, Kakuyomu, etc.)');
      return;
    }

    setIsInspecting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setInspectResult(null);

    try {
      const res = await inspectScraperUrl(trimmed);
      if (res.success && res.chapters.length > 0) {
        setInspectResult(res);
        setRangeStart(1);
        setRangeEnd(Math.min(res.total_chapters, 20));
        setSelectedChapterIndices(new Set(res.chapters.map((c) => c.index)));
      } else {
        setErrorMsg(res.error || 'No chapters found at this URL. Verify the link is a valid novel TOC.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Inspection failed. Check network or server logs.');
    } finally {
      setIsInspecting(false);
    }
  };

  const toggleChapterSelection = (index: number) => {
    setSelectedChapterIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAllChapters = () => {
    if (!inspectResult) return;
    setSelectedChapterIndices(new Set(inspectResult.chapters.map((c) => c.index)));
  };

  const deselectAllChapters = () => {
    setSelectedChapterIndices(new Set());
  };

  const selectFirstNChapters = (n: number) => {
    if (!inspectResult) return;
    const indices = inspectResult.chapters.slice(0, n).map((c) => c.index);
    setSelectedChapterIndices(new Set(indices));
  };

  const handleStartScrape = async () => {
    if (!activeProjectPath) {
      setErrorMsg('No active project selected.');
      return;
    }

    if (!inspectResult || inspectResult.chapters.length === 0) {
      setErrorMsg('Please inspect a valid novel URL first.');
      return;
    }

    const targetFolder =
      selectedFolder === '__new__' ? customFolderName.trim() : selectedFolder;

    if (selectedFolder === '__new__' && !targetFolder) {
      setErrorMsg('Please provide a name for the new folder.');
      return;
    }

    let indicesToScrape: number[] | undefined;
    let sChap: number | undefined;
    let eChap: number | undefined;

    if (selectionMode === 'all') {
      // Scrape all
    } else if (selectionMode === 'range') {
      sChap = rangeStart;
      eChap = rangeEnd;
    } else if (selectionMode === 'custom') {
      indicesToScrape = Array.from(selectedChapterIndices);
      if (indicesToScrape.length === 0) {
        setErrorMsg('Please select at least one chapter to scrape.');
        return;
      }
    }

    setIsScraping(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const startRes = await startScraperExtract({
        url: inspectResult.url,
        projectPath: activeProjectPath,
        folder: targetFolder,
        chapterIndices: indicesToScrape,
        startChapter: sChap,
        endChapter: eChap,
        concurrency,
        includeFrontmatter,
        overwrite,
      });

      const taskId = startRes.task_id;

      // Poll status every 1 second until completed or failed
      const pollInterval = window.setInterval(async () => {
        try {
          const status = await fetchScraperStatus(taskId);
          setScraperStatus(status);

          if (status.status === 'completed') {
            window.clearInterval(pollInterval);
            setIsScraping(false);
            setSuccessMsg(status.message || `Successfully scraped ${status.completed_files.length} chapters!`);
            onUploadSuccess({
              folder: targetFolder,
              uploadedCount: status.completed_files.length,
            });
            setTimeout(() => {
              onClose();
            }, 1500);
          } else if (status.status === 'failed') {
            window.clearInterval(pollInterval);
            setIsScraping(false);
            setErrorMsg(status.error || 'Scraping failed during extraction.');
          }
        } catch (e: any) {
          window.clearInterval(pollInterval);
          setIsScraping(false);
          setErrorMsg(e.message || 'Failed to poll scraper status.');
        }
      }, 1000);
    } catch (err: any) {
      setIsScraping(false);
      setErrorMsg(err.message || 'Failed to initiate scraping task.');
    }
  };

  // --------------------------------------------------------------------------
  // eBook (EPUB & PDF) Handlers
  // --------------------------------------------------------------------------

  const handleSelectEbookFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'epub' && ext !== 'pdf') {
      setErrorMsg('Please select a valid .epub or .pdf file.');
      return;
    }
    setEbookFile(file);
    setIsInspectingEbook(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await inspectEbook(file);
      setEbookInspectResult(res);
      setEbookRangeStart(1);
      setEbookRangeEnd(res.total_chapters || 10);
      setSelectedEbookIndices(new Set(res.chapters.map((c) => c.index)));
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to inspect eBook file');
      setEbookInspectResult(null);
    } finally {
      setIsInspectingEbook(false);
    }
  };

  const toggleEbookChapterSelection = (index: number) => {
    setSelectedEbookIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAllEbookChapters = () => {
    if (!ebookInspectResult) return;
    setSelectedEbookIndices(new Set(ebookInspectResult.chapters.map((c) => c.index)));
  };

  const deselectAllEbookChapters = () => {
    setSelectedEbookIndices(new Set());
  };

  const handleImportEbook = async () => {
    if (!activeProjectPath) {
      setErrorMsg('No active project selected.');
      return;
    }
    if (!ebookFile || !ebookInspectResult) {
      setErrorMsg('Please select an eBook file to import.');
      return;
    }

    const targetFolder =
      selectedFolder === '__new__' ? customFolderName.trim() : selectedFolder;

    if (selectedFolder === '__new__' && !targetFolder) {
      setErrorMsg('Please provide a name for the new folder.');
      return;
    }

    let startCh: number | undefined;
    let endCh: number | undefined;
    let indicesStr: string | undefined;

    if (ebookSelectionMode === 'range') {
      startCh = ebookRangeStart;
      endCh = ebookRangeEnd;
    } else if (ebookSelectionMode === 'custom') {
      indicesStr = Array.from(selectedEbookIndices).join(',');
      if (!indicesStr) {
        setErrorMsg('Please select at least one chapter to import.');
        return;
      }
    }

    setIsImportingEbook(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const result = await importEbook(ebookFile, {
        project_path: activeProjectPath,
        folder: targetFolder === 'raw_chapters' ? undefined : targetFolder,
        start_chapter: startCh,
        end_chapter: endCh,
        selected_indices: indicesStr,
        overwrite: overwrite,
        extract_images: ebookExtractImages,
      });

      setSuccessMsg(result.message || `Successfully imported ${result.imported_count} chapters.`);
      onUploadSuccess({ folder: targetFolder, uploadedCount: result.imported_count });
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import eBook chapters');
    } finally {
      setIsImportingEbook(false);
    }
  };

  const effectiveFolderDisplay =
    selectedFolder === '__new__'
      ? customFolderName.trim() || 'new_folder'
      : selectedFolder;

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150 font-sans">
      <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-xl w-full overflow-hidden shadow-2xl flex flex-col max-h-[92vh]">
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
            disabled={isUploading || isScraping}
            className="p-1 rounded-[2px] text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#383330] transition-colors cursor-pointer disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-[#3f3a36] bg-[#24201d] px-5 pt-2 gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('local')}
            disabled={isUploading || isScraping}
            className={`pb-2 px-3 text-xs font-mono font-medium transition-colors border-b-2 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
              activeTab === 'local'
                ? 'border-[#f7f5f0] text-[#f7f5f0]'
                : 'border-transparent text-[#857d75] hover:text-[#b0a89f]'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Local Files
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('url')}
            disabled={isUploading || isScraping}
            className={`pb-2 px-3 text-xs font-mono font-medium transition-colors border-b-2 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
              activeTab === 'url'
                ? 'border-[#d9a05b] text-[#f7f5f0]'
                : 'border-transparent text-[#857d75] hover:text-[#b0a89f]'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-[#d9a05b]" />
            Extract from URL <span className="text-[10px] text-[#d9a05b] font-bold">✨</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('ebook')}
            disabled={isUploading || isScraping || isImportingEbook}
            className={`pb-2 px-3 text-xs font-mono font-medium transition-colors border-b-2 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
              activeTab === 'ebook'
                ? 'border-[#94a8c9] text-[#f7f5f0]'
                : 'border-transparent text-[#857d75] hover:text-[#b0a89f]'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-[#94a8c9]" />
            eBook (.epub / .pdf) <span className="text-[10px] text-[#94a8c9] font-bold">📚</span>
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

        {/* Tab 1: Local Files */}
        {activeTab === 'local' && (
          <form onSubmit={handleUploadLocal} className="p-5 space-y-3.5 text-xs overflow-y-auto flex-1">
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
        )}

        {/* Tab 2: Extract from URL (Novel-Scraper Integration) */}
        {activeTab === 'url' && (
          <div className="p-5 space-y-3.5 text-xs overflow-y-auto flex-1">
            {/* Scraper Status Badge if not configured */}
            {scraperAvailable === false && (
              <div className="p-2.5 bg-[#382b22] border border-[#d9a05b]/40 rounded-[3px] text-[#f2be80] text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#d9a05b]" />
                <div>
                  <span className="font-semibold">Novel-Scraper submodule not found.</span>
                  <p className="text-[11px] text-[#d9a05b]/80 mt-0.5">
                    Please ensure the submodule is initialized with{' '}
                    <code className="bg-[#24201d] px-1 py-0.5 rounded text-[#f7f5f0]">
                      git submodule update --init --recursive
                    </code>{' '}
                    or configure <code className="bg-[#24201d] px-1 py-0.5 rounded text-[#f7f5f0]">NOVEL_SCRAPER_PATH</code> in your .env file.
                  </p>
                </div>
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
                disabled={isScraping}
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
                      disabled={isScraping}
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

            {/* URL Input Row */}
            <div className="space-y-1">
              <label className="text-[#b0a89f] font-mono text-[11px] flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-[#857d75]" />
                  Webnovel URL (TOC or Chapter)
                </span>
                <span className="text-[10px] text-[#857d75]">
                  Supports Syosetu, Kakuyomu, Dek-D, Nekopost, etc.
                </span>
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://ncode.syosetu.com/n2273dh/ or https://kakuyomu.jp/works/..."
                  value={scraperUrl}
                  onChange={(e) => setScraperUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleInspectUrl())}
                  disabled={isScraping || isInspecting}
                  className="flex-1 bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] font-mono placeholder:text-[#5c554e]"
                />
                <button
                  type="button"
                  onClick={handleInspectUrl}
                  disabled={isInspecting || isScraping || !scraperUrl.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] rounded-[3px] border border-[#3f3a36] text-xs font-mono transition-colors disabled:opacity-50 cursor-pointer shrink-0 font-medium"
                >
                  {isInspecting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Inspecting...
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5 text-[#d9a05b]" />
                      Inspect TOC
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Discovered Novel Preview Card */}
            {inspectResult && (
              <div className="p-3 bg-[#24201d] border border-[#3f3a36] rounded-[4px] space-y-3 animate-in fade-in duration-150">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5 flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="px-1.5 py-0.5 rounded-[2px] bg-[#383330] border border-[#4a433d] text-[10px] font-mono font-semibold text-[#d9a05b]">
                        {inspectResult.page_type || 'TOC'}
                      </span>
                      <h3 className="text-xs font-bold text-[#f7f5f0] truncate">
                        {inspectResult.novel_title}
                      </h3>
                    </div>
                    {inspectResult.author && (
                      <p className="text-[11px] text-[#b0a89f]">
                        Author: <span className="text-[#f7f5f0]">{inspectResult.author}</span>
                      </p>
                    )}
                  </div>
                  <span className="shrink-0 px-2 py-0.5 rounded-[3px] bg-[#272f26] border border-[#7fa678]/40 text-[#a5c49f] font-mono text-xs font-semibold">
                    {inspectResult.total_chapters} Chapters
                  </span>
                </div>

                {inspectResult.description && (
                  <p className="text-[11px] text-[#857d75] line-clamp-2 italic border-t border-[#383330] pt-2">
                    "{inspectResult.description}"
                  </p>
                )}

                {/* Chapter Selection Mode */}
                <div className="space-y-2 pt-1 border-t border-[#383330]">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-[#b0a89f] font-semibold flex items-center gap-1">
                      <BookOpen className="w-3 h-3 text-[#857d75]" />
                      Chapter Selection
                    </span>
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-1 text-[#b0a89f] cursor-pointer">
                        <input
                          type="radio"
                          name="selectionMode"
                          checked={selectionMode === 'all'}
                          onChange={() => setSelectionMode('all')}
                          disabled={isScraping}
                          className="accent-[#f7f5f0]"
                        />
                        <span>All ({inspectResult.total_chapters})</span>
                      </label>
                      <label className="flex items-center gap-1 text-[#b0a89f] cursor-pointer">
                        <input
                          type="radio"
                          name="selectionMode"
                          checked={selectionMode === 'range'}
                          onChange={() => setSelectionMode('range')}
                          disabled={isScraping}
                          className="accent-[#f7f5f0]"
                        />
                        <span>Range</span>
                      </label>
                      <label className="flex items-center gap-1 text-[#b0a89f] cursor-pointer">
                        <input
                          type="radio"
                          name="selectionMode"
                          checked={selectionMode === 'custom'}
                          onChange={() => setSelectionMode('custom')}
                          disabled={isScraping}
                          className="accent-[#f7f5f0]"
                        />
                        <span>Custom ({selectedChapterIndices.size})</span>
                      </label>
                    </div>
                  </div>

                  {/* Range Selector */}
                  {selectionMode === 'range' && (
                    <div className="flex items-center gap-2 bg-[#2b2622] p-2 rounded-[3px] border border-[#3f3a36] font-mono text-xs">
                      <span className="text-[#857d75]">From chapter:</span>
                      <input
                        type="number"
                        min={1}
                        max={inspectResult.total_chapters}
                        value={rangeStart}
                        onChange={(e) => setRangeStart(parseInt(e.target.value) || 1)}
                        disabled={isScraping}
                        className="w-16 bg-[#24201d] border border-[#3f3a36] rounded px-1.5 py-0.5 text-center text-[#f7f5f0] text-xs"
                      />
                      <span className="text-[#857d75]">to:</span>
                      <input
                        type="number"
                        min={rangeStart}
                        max={inspectResult.total_chapters}
                        value={rangeEnd}
                        onChange={(e) => setRangeEnd(parseInt(e.target.value) || rangeStart)}
                        disabled={isScraping}
                        className="w-16 bg-[#24201d] border border-[#3f3a36] rounded px-1.5 py-0.5 text-center text-[#f7f5f0] text-xs"
                      />
                      <span className="text-[#b0a89f] ml-auto text-[11px]">
                        ({Math.max(0, rangeEnd - rangeStart + 1)} chapters)
                      </span>
                    </div>
                  )}

                  {/* Custom Selection List */}
                  {selectionMode === 'custom' && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[10px] font-mono text-[#857d75]">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={selectAllChapters}
                            disabled={isScraping}
                            className="hover:text-[#f7f5f0] transition-colors"
                          >
                            All
                          </button>
                          <span>•</span>
                          <button
                            type="button"
                            onClick={deselectAllChapters}
                            disabled={isScraping}
                            className="hover:text-[#f7f5f0] transition-colors"
                          >
                            None
                          </button>
                          <span>•</span>
                          <button
                            type="button"
                            onClick={() => selectFirstNChapters(10)}
                            disabled={isScraping}
                            className="hover:text-[#f7f5f0] transition-colors"
                          >
                            First 10
                          </button>
                          <span>•</span>
                          <button
                            type="button"
                            onClick={() => selectFirstNChapters(50)}
                            disabled={isScraping}
                            className="hover:text-[#f7f5f0] transition-colors"
                          >
                            First 50
                          </button>
                        </div>
                        <span>{selectedChapterIndices.size} selected</span>
                      </div>

                      <div className="max-h-36 overflow-y-auto space-y-1 pr-1 rounded-[3px] border border-[#3f3a36] bg-[#2b2622] p-1.5">
                        {inspectResult.chapters.map((ch) => {
                          const isChecked = selectedChapterIndices.has(ch.index);
                          return (
                            <div
                              key={ch.index}
                              onClick={() => !isScraping && toggleChapterSelection(ch.index)}
                              className={`flex items-center gap-2 py-1 px-2 rounded-[2px] cursor-pointer text-xs font-mono transition-colors ${
                                isChecked
                                  ? 'bg-[#383330] text-[#f7f5f0]'
                                  : 'text-[#857d75] hover:bg-[#332e2a] hover:text-[#b0a89f]'
                              }`}
                            >
                              {isChecked ? (
                                <CheckSquare className="w-3.5 h-3.5 text-[#d9a05b] shrink-0" />
                              ) : (
                                <Square className="w-3.5 h-3.5 text-[#5c554e] shrink-0" />
                              )}
                              <span className="w-8 shrink-0 text-[#857d75]">#{ch.index}</span>
                              <span className="truncate flex-1">{ch.title}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Additional Settings */}
                <div className="flex items-center justify-between pt-1 border-t border-[#383330] text-[11px] font-mono text-[#857d75]">
                  <div className="flex items-center gap-1.5">
                    <Sliders className="w-3 h-3 text-[#857d75]" />
                    <span>Workers:</span>
                    <select
                      value={concurrency}
                      onChange={(e) => setConcurrency(parseInt(e.target.value) || 3)}
                      disabled={isScraping}
                      className="bg-[#2b2622] border border-[#3f3a36] rounded px-1.5 py-0.5 text-[#f7f5f0] text-xs focus:outline-none"
                    >
                      {[1, 2, 3, 5, 8, 10].map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-1.5 cursor-pointer text-[#b0a89f]">
                      <input
                        type="checkbox"
                        checked={includeFrontmatter}
                        onChange={(e) => setIncludeFrontmatter(e.target.checked)}
                        disabled={isScraping}
                        className="rounded accent-[#f7f5f0]"
                      />
                      <span>YAML Frontmatter</span>
                    </label>

                    <label className="flex items-center gap-1.5 cursor-pointer text-[#b0a89f]">
                      <input
                        type="checkbox"
                        checked={overwrite}
                        onChange={(e) => setOverwrite(e.target.checked)}
                        disabled={isScraping}
                        className="rounded accent-[#f7f5f0]"
                      />
                      <span>Overwrite existing</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* Scraping Progress Panel */}
            {isScraping && scraperStatus && (
              <div className="p-3 bg-[#24201d] border border-[#d9a05b]/40 rounded-[4px] space-y-2 animate-in fade-in">
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="font-semibold text-[#f7f5f0] flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-[#d9a05b]" />
                    Downloading Chapters...
                  </span>
                  <span className="text-[#d9a05b] font-bold">
                    {scraperStatus.progress_percent}%
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full h-1.5 bg-[#383330] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#d9a05b] transition-all duration-300"
                    style={{ width: `${Math.max(5, scraperStatus.progress_percent)}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-[#857d75]">
                  <span className="truncate pr-2">
                    {scraperStatus.current_title ? `Current: ${scraperStatus.current_title}` : scraperStatus.message}
                  </span>
                  {scraperStatus.total_chapters > 0 && (
                    <span className="shrink-0">
                      {scraperStatus.current_chapter}/{scraperStatus.total_chapters}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Footer Actions */}
            <div className="pt-3 border-t border-[#3f3a36] flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isScraping || isInspecting}
                className="px-3.5 py-1.5 rounded-[3px] bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleStartScrape}
                disabled={isScraping || isInspecting || !inspectResult || scraperAvailable === false}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[3px] bg-[#d9a05b] hover:bg-[#e6b170] text-[#24201d] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                {isScraping ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Scraping...
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5" />
                    Scrape & Import
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Tab 3: eBook (EPUB & PDF) */}
        {activeTab === 'ebook' && (
          <div className="p-5 space-y-4 text-xs overflow-y-auto flex-1">
            {/* File Dropzone or Selected Card */}
            {!ebookInspectResult ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleSelectEbookFile(e.dataTransfer.files[0]);
                  }
                }}
                onClick={() => ebookFileInputRef.current?.click()}
                className={`p-6 border-2 border-dashed rounded-[4px] flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-[#94a8c9] bg-[#94a8c9]/10'
                    : 'border-[#3f3a36] hover:border-[#857d75] bg-[#24201d]'
                }`}
              >
                <input
                  ref={ebookFileInputRef}
                  type="file"
                  accept=".epub,.pdf"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleSelectEbookFile(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />

                {isInspectingEbook ? (
                  <div className="flex flex-col items-center gap-2 py-4">
                    <Loader2 className="w-8 h-8 text-[#94a8c9] animate-spin" />
                    <span className="font-mono text-xs text-[#f7f5f0]">
                      Analyzing eBook structure with PyMuPDF & EPUB parser...
                    </span>
                    <span className="text-[11px] text-[#857d75]">
                      Extracting Table of Contents, Thai diacritics, and illustrations
                    </span>
                  </div>
                ) : (
                  <>
                    <BookOpen className="w-8 h-8 text-[#94a8c9] mb-2" />
                    <span className="font-mono text-xs text-[#f7f5f0] font-semibold">
                      Drop .epub or .pdf novel file here, or browse
                    </span>
                    <span className="text-[11px] text-[#857d75] mt-1 max-w-sm">
                      Automatic chapter extraction, PyMuPDF complex script parsing (Thai/CJK), and illustration detection
                    </span>
                    <span className="inline-block mt-3 px-2 py-0.5 bg-[#383330] text-[#94a8c9] text-[10px] font-mono rounded-[2px] border border-[#3f3a36]">
                      Supports EPUB2, EPUB3, and PDF
                    </span>
                  </>
                )}
              </div>
            ) : (
              /* Inspected Book Preview Card */
              <div className="space-y-3">
                <div className="p-3 bg-[#24201d] border border-[#3f3a36] rounded-[3px] flex gap-3">
                  {ebookInspectResult.has_cover && ebookInspectResult.cover_base64 ? (
                    <img
                      src={ebookInspectResult.cover_base64}
                      alt="Cover Art"
                      className="w-16 h-24 object-cover rounded-[2px] border border-[#3f3a36] shrink-0 shadow-md"
                    />
                  ) : (
                    <div className="w-16 h-24 bg-[#383330] rounded-[2px] border border-[#3f3a36] flex flex-col items-center justify-center text-[#857d75] shrink-0">
                      <BookOpen className="w-6 h-6" />
                      <span className="text-[9px] mt-1 font-mono uppercase">No Cover</span>
                    </div>
                  )}

                  <div className="flex-1 min-w-0 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] px-1.5 py-0.2 bg-[#94a8c9]/20 text-[#94a8c9] rounded-[2px] font-mono uppercase font-bold">
                          {ebookInspectResult.format.toUpperCase()}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 bg-[#7fa678]/20 text-[#a5c49f] rounded-[2px] font-mono">
                          {ebookInspectResult.total_chapters} Chapters
                        </span>
                      </div>
                      <h3 className="font-mono font-bold text-sm text-[#f7f5f0] truncate mt-1">
                        {ebookInspectResult.title}
                      </h3>
                      {ebookInspectResult.author && (
                        <p className="text-[11px] text-[#b0a89f] truncate">
                          Author: {ebookInspectResult.author}
                        </p>
                      )}
                      <p className="text-[11px] text-[#857d75] truncate mt-0.5">
                        File: {ebookFile?.name}
                      </p>
                    </div>

                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          setEbookFile(null);
                          setEbookInspectResult(null);
                        }}
                        className="text-[11px] text-[#94a8c9] hover:underline cursor-pointer font-mono"
                      >
                        &larr; Choose different file
                      </button>
                    </div>
                  </div>
                </div>

                {/* Destination Folder */}
                <div className="space-y-1">
                  <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5">
                    <Folder className="w-3.5 h-3.5 text-[#857d75]" />
                    Destination Folder in Project
                  </label>
                  <select
                    value={selectedFolder}
                    onChange={(e) => setSelectedFolder(e.target.value)}
                    disabled={isImportingEbook}
                    className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-[#f7f5f0] text-xs focus:outline-none focus:border-[#b0a89f] cursor-pointer disabled:opacity-50 font-mono"
                  >
                    {folders.map((f) => (
                      <option key={f} value={f}>
                        {f} {f === defaultFolder ? '(Default Raw Directory)' : '(Volume Subfolder)'}
                      </option>
                    ))}
                    <option value="__new__">+ Create New Subfolder / Volume...</option>
                  </select>

                  {selectedFolder === '__new__' && (
                    <div className="pt-1.5 flex items-center gap-2">
                      <FolderPlus className="w-3.5 h-3.5 text-[#d9a05b] shrink-0" />
                      <input
                        type="text"
                        value={customFolderName}
                        onChange={(e) => setCustomFolderName(e.target.value)}
                        placeholder="e.g. Volume_01 or Arc_Prologue"
                        disabled={isImportingEbook}
                        className="flex-1 bg-[#24201d] border border-[#d9a05b]/60 rounded-[3px] px-2.5 py-1 text-[#f7f5f0] text-xs font-mono focus:outline-none focus:border-[#d9a05b]"
                      />
                    </div>
                  )}
                </div>

                {/* Chapter Selection Mode */}
                <div className="space-y-2 pt-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[#b0a89f] font-mono text-[11px] flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-[#857d75]" />
                      Chapter Ingestion Selection
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setEbookSelectionMode('all')}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-[2px] transition-colors cursor-pointer ${
                          ebookSelectionMode === 'all'
                            ? 'bg-[#94a8c9] text-[#1c1815] font-bold'
                            : 'bg-[#383330] text-[#b0a89f] hover:text-[#f7f5f0]'
                        }`}
                      >
                        All ({ebookInspectResult.total_chapters})
                      </button>
                      <button
                        type="button"
                        onClick={() => setEbookSelectionMode('range')}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-[2px] transition-colors cursor-pointer ${
                          ebookSelectionMode === 'range'
                            ? 'bg-[#94a8c9] text-[#1c1815] font-bold'
                            : 'bg-[#383330] text-[#b0a89f] hover:text-[#f7f5f0]'
                        }`}
                      >
                        Range
                      </button>
                      <button
                        type="button"
                        onClick={() => setEbookSelectionMode('custom')}
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-[2px] transition-colors cursor-pointer ${
                          ebookSelectionMode === 'custom'
                            ? 'bg-[#94a8c9] text-[#1c1815] font-bold'
                            : 'bg-[#383330] text-[#b0a89f] hover:text-[#f7f5f0]'
                        }`}
                      >
                        Custom ({selectedEbookIndices.size})
                      </button>
                    </div>
                  </div>

                  {ebookSelectionMode === 'range' && (
                    <div className="p-2.5 bg-[#24201d] border border-[#3f3a36] rounded-[3px] flex items-center gap-2">
                      <span className="text-[#857d75] font-mono">From Chapter:</span>
                      <input
                        type="number"
                        min={1}
                        max={ebookInspectResult.total_chapters}
                        value={ebookRangeStart}
                        onChange={(e) => setEbookRangeStart(parseInt(e.target.value, 10) || 1)}
                        className="w-16 bg-[#2b2622] border border-[#3f3a36] rounded-[2px] px-2 py-0.5 text-center font-mono text-[#f7f5f0]"
                      />
                      <span className="text-[#857d75] font-mono">To:</span>
                      <input
                        type="number"
                        min={ebookRangeStart}
                        max={ebookInspectResult.total_chapters}
                        value={ebookRangeEnd}
                        onChange={(e) => setEbookRangeEnd(parseInt(e.target.value, 10) || ebookRangeStart)}
                        className="w-16 bg-[#2b2622] border border-[#3f3a36] rounded-[2px] px-2 py-0.5 text-center font-mono text-[#f7f5f0]"
                      />
                    </div>
                  )}

                  {ebookSelectionMode === 'custom' && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] text-[#857d75]">
                        <span className="font-mono">
                          Selected {selectedEbookIndices.size} of {ebookInspectResult.total_chapters}
                        </span>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={selectAllEbookChapters}
                            className="hover:underline text-[#94a8c9]"
                          >
                            Select All
                          </button>
                          <span>&bull;</span>
                          <button
                            type="button"
                            onClick={deselectAllEbookChapters}
                            className="hover:underline text-[#94a8c9]"
                          >
                            Deselect All
                          </button>
                        </div>
                      </div>

                      <div className="max-h-36 overflow-y-auto border border-[#3f3a36] rounded-[3px] bg-[#24201d] divide-y divide-[#3f3a36]/50">
                        {ebookInspectResult.chapters.map((ch) => {
                          const isChecked = selectedEbookIndices.has(ch.index);
                          return (
                            <div
                              key={ch.index}
                              onClick={() => toggleEbookChapterSelection(ch.index)}
                              className={`p-2 flex items-center justify-between cursor-pointer hover:bg-[#2b2622] transition-colors ${
                                isChecked ? 'bg-[#383330]/40' : ''
                              }`}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {isChecked ? (
                                  <CheckSquare className="w-3.5 h-3.5 text-[#94a8c9] shrink-0" />
                                ) : (
                                  <Square className="w-3.5 h-3.5 text-[#857d75] shrink-0" />
                                )}
                                <span className="font-mono text-xs text-[#f7f5f0] truncate">
                                  {ch.title}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-[10px] text-[#857d75] shrink-0 font-mono">
                                {ch.has_images && (
                                  <span className="text-[#d9a05b] flex items-center gap-0.5">
                                    <ImageIcon className="w-3 h-3" />
                                    img
                                  </span>
                                )}
                                <span>{ch.word_count.toLocaleString()} words</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Import Options */}
                <div className="p-2.5 bg-[#24201d] border border-[#3f3a36] rounded-[3px] space-y-2">
                  <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ebookExtractImages}
                      onChange={(e) => setEbookExtractImages(e.target.checked)}
                      className="rounded-[2px] accent-[#94a8c9] cursor-pointer"
                    />
                    <span>Extract illustrations & cover to project assets/ folder</span>
                  </label>

                  <label className="flex items-center gap-2 text-[#dad2c1] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={overwrite}
                      onChange={(e) => setOverwrite(e.target.checked)}
                      className="rounded-[2px] accent-[#94a8c9] cursor-pointer"
                    />
                    <span>Overwrite existing chapter files if numbered identically</span>
                  </label>
                </div>
              </div>
            )}

            {/* Action Footer */}
            <div className="pt-3 border-t border-[#3f3a36] flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isImportingEbook || isInspectingEbook}
                className="px-3.5 py-1.5 rounded-[3px] bg-[#383330] hover:bg-[#3f3a36] text-[#f7f5f0] text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleImportEbook}
                disabled={isImportingEbook || isInspectingEbook || !ebookInspectResult}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-[3px] bg-[#94a8c9] hover:bg-[#a9bcdb] text-[#1c1815] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                {isImportingEbook ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Importing Chapters...</span>
                  </>
                ) : (
                  <>
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>
                      Import{' '}
                      {ebookSelectionMode === 'custom'
                        ? `${selectedEbookIndices.size} Chapters`
                        : ebookSelectionMode === 'range'
                        ? `${Math.max(0, ebookRangeEnd - ebookRangeStart + 1)} Chapters`
                        : `${ebookInspectResult?.total_chapters || ''} Chapters`}
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
