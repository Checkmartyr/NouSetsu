import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Download, FolderPlus, LoaderCircle, Search, Sparkles, X } from 'lucide-react';
import { createProject } from '../services/apiClient';
import {
  checkScraperAvailability,
  fetchScraperStatus,
  inspectScraperUrl,
  startScraperExtract,
} from '../services/dashboardApi';
import { ScraperInspectResult, ScraperStatusResult } from '../types/dashboard';
import { ProjectMeta } from '../types/trace';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: ProjectMeta) => void;
  projectsDirName?: string;
}

const generateProjectName = (value: string) =>
  value.trim().replace(/[<>:"/\\|?*]/g, '_').replace(/^[. ]+|[. ]+$/g, '') || 'new_novel';

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
  const [importFromUrl, setImportFromUrl] = useState(false);
  const [scraperAvailable, setScraperAvailable] = useState<boolean | null>(null);
  const [scraperUrl, setScraperUrl] = useState('');
  const [inspectResult, setInspectResult] = useState<ScraperInspectResult | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [selectionMode, setSelectionMode] = useState<'all' | 'range'>('all');
  const [rangeStart, setRangeStart] = useState(1);
  const [rangeEnd, setRangeEnd] = useState(20);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatusResult | null>(null);
  const [createdProject, setCreatedProject] = useState<ProjectMeta | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    setTitle('');
    setFolderName('');
    setSourceLanguage('Japanese');
    setTargetLanguage('Thai');
    setGenre('general');
    setModel('gemini-3.5-flash-lite');
    setErrorMsg(null);
    setImportFromUrl(false);
    setScraperAvailable(null);
    setScraperUrl('');
    setInspectResult(null);
    setIsInspecting(false);
    setSelectionMode('all');
    setRangeStart(1);
    setRangeEnd(20);
    setScraperStatus(null);
    setCreatedProject(null);

    let cancelled = false;
    checkScraperAvailability().then((result) => {
      if (!cancelled) setScraperAvailable(result.available);
    });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleInspectUrl = async () => {
    const trimmed = scraperUrl.trim();
    if (!trimmed) {
      setErrorMsg('Enter a webnovel URL before inspecting it.');
      return;
    }

    setIsInspecting(true);
    setErrorMsg(null);
    setInspectResult(null);
    try {
      const result = await inspectScraperUrl(trimmed);
      if (!result.success || result.chapters.length === 0) {
        setErrorMsg(result.error || 'No chapters were found at this URL.');
        return;
      }
      setInspectResult(result);
      setRangeStart(1);
      setRangeEnd(Math.min(result.total_chapters || result.chapters.length, 20));
      if (result.novel_title && result.novel_title !== 'Unknown Novel') {
        const projectTitle = title.trim() || result.novel_title;
        if (!title.trim()) setTitle(result.novel_title);
        if (!folderName.trim()) {
          setFolderName(generateProjectName(result.romanized_title || projectTitle));
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to inspect novel URL.');
    } finally {
      setIsInspecting(false);
    }
  };

  const importChapters = async (project: ProjectMeta) => {
    if (!inspectResult) throw new Error('Inspect the novel URL before importing chapters.');

    const startRes = await startScraperExtract({
      url: inspectResult.url,
      projectPath: project.path,
      folder: 'raw_chapters',
      startChapter: selectionMode === 'range' ? rangeStart : undefined,
      endChapter: selectionMode === 'range' ? rangeEnd : undefined,
      concurrency: 3,
    });

    let status = await fetchScraperStatus(startRes.task_id);
    setScraperStatus(status);
    while (status.status === 'pending' || status.status === 'running') {
      await new Promise<void>((resolve) => window.setTimeout(resolve, 1000));
      status = await fetchScraperStatus(startRes.task_id);
      setScraperStatus(status);
    }

    if (status.status !== 'completed') {
      throw new Error(status.error || status.message || 'Chapter import failed.');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMsg('Please enter a novel title.');
      return;
    }
    if (importFromUrl) {
      if (scraperAvailable !== true) {
        setErrorMsg('Novel-Scraper is unavailable. Initialize the submodule before importing chapters.');
        return;
      }
      if (!inspectResult || inspectResult.url !== scraperUrl.trim()) {
        setErrorMsg('Inspect the current novel URL before creating the project.');
        return;
      }
      const maxChapter = inspectResult?.total_chapters || inspectResult?.chapters.length || 0;
      if (selectionMode === 'range' && (rangeStart < 1 || rangeEnd < rangeStart || rangeEnd > maxChapter)) {
        setErrorMsg('Enter a valid chapter range.');
        return;
      }
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    setScraperStatus(null);

    let project = createdProject;
    let createdDuringSubmit = false;
    try {
      if (!project) {
        const res = await createProject({
          title: title.trim(),
          folder_name: folderName.trim() || undefined,
          source_language: sourceLanguage.trim() || 'Japanese',
          target_language: targetLanguage.trim() || 'Thai',
          genre: genre.trim() || 'general',
          model: model.trim() || undefined,
        });
        if (!res.success || !res.active_project) {
          throw new Error('Project creation did not return active project details.');
        }
        project = res.active_project;
        createdDuringSubmit = true;
      }

      if (importFromUrl) {
        if (createdDuringSubmit) {
          setCreatedProject(project);
          await onProjectCreated(project);
        }
        await importChapters(project);
      }

      if (!importFromUrl) {
        await onProjectCreated(project);
      }
      setCreatedProject(null);
      onClose();
    } catch (err: any) {
      const message = err.message || 'Failed to create novel project.';
      setErrorMsg(project && importFromUrl
        ? `Project created, but chapter import failed: ${message}`
        : message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return;
    setCreatedProject(null);
    setErrorMsg(null);
    onClose();
  };

  const computedFolder = folderName.trim() || generateProjectName(title);

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150 font-sans">
      <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-lg w-full max-h-[92vh] overflow-hidden shadow-2xl flex flex-col">
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
            onClick={handleClose}
            disabled={isSubmitting}
            className="p-1 rounded-[2px] text-[#857d75] hover:text-[#f7f5f0] hover:bg-[#383330] transition-colors cursor-pointer disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-3.5 text-xs overflow-y-auto">
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
              Project Name <span className="text-[#857d75] font-normal">(auto-generated, editable)</span>
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

          {/* Optional URL-based project seeding */}
          <section className="border border-[#3f3a36] rounded-[3px] p-3 space-y-3">
            <label className="flex items-center gap-2 text-[#f7f5f0] font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={importFromUrl}
                onChange={(e) => setImportFromUrl(e.target.checked)}
                disabled={isSubmitting || scraperAvailable !== true || Boolean(createdProject)}
                className="accent-[#d9a05b]"
              />
              <Download className="w-3.5 h-3.5 text-[#d9a05b]" />
              Import chapters from a novel URL into raw_chapters
              {scraperAvailable === null && <span className="text-[#857d75] font-normal">(checking scraper)</span>}
            </label>

            {scraperAvailable === false && (
              <div className="flex items-start gap-2 p-2 bg-[#382b22] border border-[#d9a05b]/40 rounded-[3px] text-[#d9a05b]">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                <span className="text-[11px]">
                  Novel-Scraper is unavailable. Initialize it with{' '}
                  <code className="text-[#f7f5f0]">git submodule update --init --recursive</code>{' '}
                  or configure <code className="text-[#f7f5f0]">NOVEL_SCRAPER_PATH</code>.
                </span>
              </div>
            )}

            {importFromUrl && scraperAvailable && (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={scraperUrl}
                    onChange={(e) => {
                      setScraperUrl(e.target.value);
                      setInspectResult(null);
                      setScraperStatus(null);
                    }}
                    disabled={isSubmitting || Boolean(createdProject)}
                    placeholder="https://ncode.syosetu.com/... or Kakuyomu URL"
                    className="flex-1 min-w-0 bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-2 text-[#f7f5f0] placeholder-[#857d75] focus:outline-none focus:border-[#b0a89f] text-xs font-mono disabled:opacity-60"
                  />
                  <button
                    type="button"
                    onClick={handleInspectUrl}
                    disabled={isInspecting || isSubmitting || Boolean(createdProject) || !scraperUrl.trim()}
                    className="flex items-center gap-1.5 px-2.5 bg-[#383330] border border-[#3f3a36] rounded-[3px] text-[#f7f5f0] hover:bg-[#3f3a36] disabled:opacity-50"
                  >
                    {isInspecting ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    Inspect
                  </button>
                </div>

                {inspectResult && (
                  <div className="space-y-2.5 p-2.5 bg-[#24201d] border border-[#3f3a36] rounded-[3px]">
                    <div className="flex items-start gap-2 text-[#b0a89f]">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <div>
                        <div className="text-[#f7f5f0] font-medium">{inspectResult.novel_title}</div>
                        <div className="text-[11px]">
                          {inspectResult.total_chapters || inspectResult.chapters.length} chapters found
                          {inspectResult.author ? ` · ${inspectResult.author}` : ''}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-[#b0a89f]">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          checked={selectionMode === 'all'}
                          onChange={() => setSelectionMode('all')}
                          disabled={isSubmitting}
                          className="accent-[#d9a05b]"
                        />
                        All chapters
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          checked={selectionMode === 'range'}
                          onChange={() => setSelectionMode('range')}
                          disabled={isSubmitting}
                          className="accent-[#d9a05b]"
                        />
                        Chapter range
                      </label>
                    </div>
                    {selectionMode === 'range' && (
                      <div className="flex items-center gap-2 text-[11px] text-[#857d75]">
                        <span>From</span>
                        <input
                          type="number"
                          min={1}
                          max={inspectResult.total_chapters || undefined}
                          value={rangeStart}
                          onChange={(e) => setRangeStart(Number(e.target.value))}
                          disabled={isSubmitting}
                          className="w-20 bg-[#2b2622] border border-[#3f3a36] rounded-[3px] p-1.5 text-[#f7f5f0]"
                        />
                        <span>to</span>
                        <input
                          type="number"
                          min={rangeStart}
                          max={inspectResult.total_chapters || undefined}
                          value={rangeEnd}
                          onChange={(e) => setRangeEnd(Number(e.target.value))}
                          disabled={isSubmitting}
                          className="w-20 bg-[#2b2622] border border-[#3f3a36] rounded-[3px] p-1.5 text-[#f7f5f0]"
                        />
                      </div>
                    )}
                  </div>
                )}

                {createdProject && (
                  <div className="text-[11px] text-[#d9a05b]">
                    Project initialized at <code className="text-[#f7f5f0]">{createdProject.path}</code>. Retry the import or close this window; the project is preserved.
                  </div>
                )}

                {scraperStatus && (scraperStatus.status === 'running' || scraperStatus.status === 'pending') && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] text-[#b0a89f]">
                      <span>{scraperStatus.message || 'Preparing chapter import...'}</span>
                      <span>{Math.round(scraperStatus.progress_percent)}%</span>
                    </div>
                    <div className="h-1.5 bg-[#24201d] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#d9a05b] transition-all"
                        style={{ width: `${Math.max(0, Math.min(100, scraperStatus.progress_percent))}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#3f3a36]">
            <button
              type="button"
              onClick={handleClose}
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
              {isSubmitting ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {isSubmitting
                ? (scraperStatus?.status === 'running' ? 'Importing Chapters...' : 'Creating...')
                : createdProject ? 'Retry Chapter Import' : importFromUrl ? 'Create & Import Chapters' : 'Initialize Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
