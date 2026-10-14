import { useEffect, useRef, useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import { isTauriDesktopRuntime } from '../services/apiBase';
import { setupRequest } from '../services/setupApi';
import { switchActiveProject, fetchActiveProject } from '../services/apiClient';
import type { ProjectMeta } from '../types/trace';

export function OpenProjectDialog({ locale, onClose, onOpened }: { locale: 'en' | 'th'; onClose: () => void; onOpened: (project: ProjectMeta) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [path, setPath] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const t = (en: string, th: string) => locale === 'th' ? th : en;
  useEffect(() => { ref.current?.showModal(); }, []);
  const choose = async () => {
    setError('');
    try {
      if (isTauriDesktopRuntime()) {
        const result = await open({ directory: true, multiple: false });
        if (typeof result === 'string') setPath(result);
      } else {
        const result = await setupRequest<{ path: string | null }>('/check', { kind: 'folder', candidate: { skip_ai: true } });
        if (result.path) setPath(result.path);
      }
    } catch { setError(t('Folder picker unavailable. Paste a folder path.', 'เลือกโฟลเดอร์ไม่ได้ กรุณาวางตำแหน่งโฟลเดอร์')); }
  };
  const load = async () => {
    setBusy(true); setError('');
    try {
      if (!await switchActiveProject(path)) throw new Error();
      const result = await fetchActiveProject();
      if (!result?.active_project) throw new Error();
      onOpened(result.active_project); onClose();
    } catch { setError(t('This folder is not a valid NouSetsu novel. Choose its project folder containing .novel.', 'โฟลเดอร์นี้ไม่ใช่โครงการนิยาย NouSetsu เลือกโฟลเดอร์โครงการที่มี .novel')); }
    finally { setBusy(false); }
  };
  return <dialog ref={ref} aria-labelledby="open-project-title" onCancel={onClose} className="setup-shell rounded-xl w-full max-w-[720px] backdrop:bg-black/60">
    <h1 id="open-project-title" className="text-2xl mb-4">{t('Open an existing novel', 'เปิดนิยายที่มีอยู่')}</h1>
    <p className="mb-4">{t('Choose the novel’s project folder. Existing chapters and settings are preserved.', 'เลือกโฟลเดอร์โครงการนิยาย บทนิยายและการตั้งค่าเดิมจะยังอยู่')}</p>
    <label className="setup-field">{t('Project folder', 'โฟลเดอร์โครงการ')}<input autoFocus value={path} onChange={event => setPath(event.target.value)} /></label>
    <button className="mt-4" disabled={busy} onClick={() => { void choose(); }}>{t('Choose folder', 'เลือกโฟลเดอร์')}</button>
    {error && <p role="alert" className="mt-4">{error}</p>}
    <footer className="setup-footer"><button onClick={onClose}>{t('Cancel', 'ยกเลิก')}</button><button className="setup-primary" disabled={busy || !path.trim()} onClick={() => { void load(); }}>{t('Open novel', 'เปิดนิยาย')}</button></footer>
  </dialog>;
}
