import { AgentPromptTrace, ChapterTraceDocument, LoadedChapter } from '../types/trace';

/**
 * Parse a JSON string representing ChapterTraceDocument
 */
export function parseChapterJson(content: string, fileName: string): ChapterTraceDocument {
  const doc = JSON.parse(content);
  if (!doc.traces || !Array.isArray(doc.traces)) {
    // If it's an array of traces directly
    if (Array.isArray(doc)) {
      return assembleDocFromTraces(doc, fileName);
    }
    throw new Error(`File ${fileName} is not a valid chapter trace document.`);
  }
  return doc as ChapterTraceDocument;
}

/**
 * Parse a JSONL string where each line is an AgentPromptTrace
 */
export function parseChapterJsonl(content: string, fileName: string): ChapterTraceDocument {
  const lines = content.split('\n');
  const traces: AgentPromptTrace[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    try {
      const trace = JSON.parse(line) as AgentPromptTrace;
      if (trace.trace_id && trace.stage) {
        traces.push(trace);
      }
    } catch {
      console.warn(`Skipping malformed line ${i + 1} in ${fileName}`);
    }
  }

  return assembleDocFromTraces(traces, fileName);
}

/**
 * Assemble ChapterTraceDocument from array of traces
 */
function assembleDocFromTraces(traces: AgentPromptTrace[], fileName: string): ChapterTraceDocument {
  // Extract metadata from traces or filename
  const match = fileName.match(/chapter_(\d+)/i);
  const chapterNum = traces[0]?.chapter_num ?? (match ? parseInt(match[1], 10) : 1);
  const chapterId = traces[0]?.chapter_id ?? `chapter_${chapterNum.toString().padStart(4, '0')}`;
  const folder = traces[0]?.folder ?? null;

  let totalDuration = 0;
  const tokenUsage = {
    input_tokens: 0,
    output_tokens: 0,
    thought_tokens: 0,
    cached_tokens: 0,
    total_tokens: 0,
  };
  const stageBreakdown: Record<string, number> = {};

  traces.forEach((t) => {
    totalDuration += t.duration_seconds || 0;
    stageBreakdown[t.stage] = (stageBreakdown[t.stage] || 0) + 1;
    if (t.token_usage) {
      tokenUsage.input_tokens += t.token_usage.input_tokens || 0;
      tokenUsage.output_tokens += t.token_usage.output_tokens || 0;
      tokenUsage.thought_tokens += t.token_usage.thought_tokens || 0;
      tokenUsage.cached_tokens += t.token_usage.cached_tokens || 0;
      tokenUsage.total_tokens += t.token_usage.total_tokens || 0;
    }
  });

  return {
    chapter_id: chapterId,
    chapter_num: chapterNum,
    folder,
    total_interactions: traces.length,
    total_duration_seconds: parseFloat(totalDuration.toFixed(3)),
    total_token_usage: tokenUsage,
    stage_breakdown: stageBreakdown,
    traces,
  };
}

/**
 * Process a collection of loaded files and group them into chapters
 */
export function groupFilesIntoChapters(
  files: { name: string; content: string; relativePath?: string }[]
): LoadedChapter[] {
  const chapterMap = new Map<string, { doc: ChapterTraceDocument; fileName: string; folder: string | null }>();

  // Prioritize .json over .jsonl for completeness
  const sortedFiles = [...files].sort((a, b) => {
    if (a.name.endsWith('.json') && !b.name.endsWith('.json')) return -1;
    if (!a.name.endsWith('.json') && b.name.endsWith('.json')) return 1;
    return 0;
  });

  for (const file of sortedFiles) {
    if (!file.name.endsWith('.json') && !file.name.endsWith('.jsonl')) continue;

    try {
      let doc: ChapterTraceDocument;
      if (file.name.endsWith('.json')) {
        doc = parseChapterJson(file.content, file.name);
      } else {
        doc = parseChapterJsonl(file.content, file.name);
      }

      // Determine folder from relative path if not in doc
      let folder = doc.folder;
      if (!folder && file.relativePath) {
        const parts = file.relativePath.split(/[\\/]/);
        if (parts.length > 1) {
          folder = parts[parts.length - 2];
          // Skip if folder is 'traces' or '.novel'
          if (folder === 'traces' || folder === '.novel') {
            folder = null;
          }
        }
      }

      const key = `${folder || 'root'}_ch${doc.chapter_num}`;
      if (!chapterMap.has(key)) {
        chapterMap.set(key, { doc, fileName: file.name, folder });
      }
    } catch (err) {
      console.error(`Failed to parse ${file.name}:`, err);
    }
  }

  const result: LoadedChapter[] = [];
  chapterMap.forEach(({ doc, fileName, folder }, key) => {
    result.push({
      id: key,
      fileName,
      folder,
      chapterNum: doc.chapter_num,
      document: doc,
    });
  });

  // Sort by folder then chapter number
  return result.sort((a, b) => {
    if (a.folder !== b.folder) {
      if (!a.folder) return -1;
      if (!b.folder) return 1;
      return a.folder.localeCompare(b.folder);
    }
    return a.chapterNum - b.chapterNum;
  });
}

/**
 * Native Directory Picker for modern browsers (Chromium / Edge / Opera)
 */
export async function openDirectoryPicker(): Promise<{ name: string; content: string; relativePath: string }[]> {
  if (!('showDirectoryPicker' in window)) {
    throw new Error('Directory Picker API is not supported in this browser. Please use the Drag-and-Drop or File Picker.');
  }

  // @ts-expect-error - File System Access API
  const dirHandle = await window.showDirectoryPicker();
  const loadedFiles: { name: string; content: string; relativePath: string }[] = [];

  async function scanDirectory(handle: any, currentPath: string) {
    for await (const entry of handle.values()) {
      if (entry.kind === 'file') {
        if (entry.name.endsWith('.json') || entry.name.endsWith('.jsonl')) {
          const file = await entry.getFile();
          const content = await file.text();
          loadedFiles.push({
            name: entry.name,
            content,
            relativePath: `${currentPath}/${entry.name}`,
          });
        }
      } else if (entry.kind === 'directory') {
        await scanDirectory(entry, `${currentPath}/${entry.name}`);
      }
    }
  }

  await scanDirectory(dirHandle, dirHandle.name);
  return loadedFiles;
}
