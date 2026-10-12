import type { ChapterItem } from '../types/dashboard';

export const chapterSortOptions = [
  { value: 'number-asc', label: 'Chapter number ↑' },
  { value: 'number-desc', label: 'Chapter number ↓' },
  { value: 'title-asc', label: 'Title A–Z' },
  { value: 'title-desc', label: 'Title Z–A' },
] as const;

export type ChapterSort = typeof chapterSortOptions[number]['value'];

export function normalizeChapterSort(value: unknown): ChapterSort {
  return chapterSortOptions.find((option) => option.value === value)?.value ?? 'number-asc';
}

export function chapterTitle(chapter: ChapterItem): string {
  return chapter.title.trim() || chapter.file_name || `Chapter ${chapter.chapter_num}`;
}

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

function compareFolders(a: string | null, b: string | null): number {
  if (!a || !b) return a ? 1 : b ? -1 : 0;
  return collator.compare(a, b) || (a < b ? -1 : a > b ? 1 : 0);
}

function compareStory(a: ChapterItem, b: ChapterItem): number {
  return compareFolders(a.folder, b.folder)
    || a.chapter_num - b.chapter_num
    || collator.compare(a.file_name, b.file_name)
    || (a.file_name < b.file_name ? -1 : a.file_name > b.file_name ? 1 : 0);
}

export function sortStoryChapters(chapters: ChapterItem[]): ChapterItem[] {
  return [...chapters].sort(compareStory);
}

export function sortDisplayChapters(chapters: ChapterItem[], sort: ChapterSort): ChapterItem[] {
  const direction = sort.endsWith('desc') ? -1 : 1;
  return [...chapters].sort((a, b) => {
    const primary = sort.startsWith('title')
      ? collator.compare(chapterTitle(a), chapterTitle(b))
      : a.chapter_num - b.chapter_num;
    return direction * primary || compareStory(a, b);
  });
}
