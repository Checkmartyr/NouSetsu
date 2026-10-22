import { useEffect, useRef, useState } from 'react';
import { BookOpen, CheckCircle2, AlertCircle, FolderOpen, ArrowRight } from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import { invoke } from '@tauri-apps/api/core';
import { isTauriDesktopRuntime } from '../services/apiBase';
import { SetupCandidate, SetupError, SetupSnapshot, setupRequest } from '../services/setupApi';
import { GLOBAL_ENV_GROUPS, GLOBAL_ENV_LABELS, GenerationSettingsEditor, ModelRouteControl, providerForRoute, modelIdForRoute } from './SettingsView';
import type { GenerationRole, ModelCatalogResult, ModelProvider } from '../types/dashboard';

const providerLabels = { gemini: 'Google Gemini', openai: 'OpenAI', openrouter: 'OpenRouter', custom: 'Custom service' };
const keyNames = { gemini: 'GEMINI_API_KEY', openai: 'OPENAI_API_KEY', openrouter: 'OPENROUTER_API_KEY', custom: 'CUSTOM_API_KEY' };
const helpLinks = {
  gemini: 'https://aistudio.google.com/apikey', openai: 'https://platform.openai.com/api-keys',
  openrouter: 'https://openrouter.ai/settings/keys', custom: '',
};
const roles: GenerationRole[] = ['extractor', 'drafter', 'critic', 'polisher', 'chronicler', 'scraper'];
const routeKeys = ['DEFAULT_MODEL', 'NOVEL_MODEL', 'NOVEL_FALLBACK_MODEL', ...roles.map(role => `NOVEL_${role.toUpperCase()}_MODEL`), 'NOVEL_RAG_RERANKER_MODEL', 'NOVEL_PROCEDURAL_REFINER_MODEL'];
const labelsTh: Record<string, string> = {
  general: 'ภาษาเริ่มต้น', models: 'โมเดลและการสร้างข้อความ', agent_extractor: 'ค้นหาตัวละครและคำศัพท์',
  agent_drafter: 'ร่างคำแปล', agent_critic: 'ตรวจสอบคำแปล', agent_polisher: 'ปรับสำนวน', agent_chronicler: 'บันทึกเรื่องราว', agent_scraper: 'นำเข้านิยายจากเว็บ',
  review: 'คุณภาพคำแปล', memory: 'ความจำและคำศัพท์', rag: 'การค้นหาข้อมูลเรื่องราว', ratelimit: 'การจำกัดความเร็ว', procedural: 'การเรียนรู้', paths: 'ตำแหน่งโฟลเดอร์',
};
const settingLabels: Record<string, [string, string]> = {
  DEFAULT_MODEL: ['Default model', 'โมเดลเริ่มต้น'], NOVEL_FALLBACK_MODEL: ['Fallback model', 'โมเดลสำรอง'],
  NOVEL_MAX_REVIEW_LOOPS: ['Maximum review passes', 'จำนวนรอบตรวจสอบสูงสุด'], NOVEL_QUALITY_THRESHOLD: ['Quality target', 'เป้าหมายคุณภาพ'],
  NOVEL_MAX_TPM: ['Tokens per minute', 'โทเคนต่อนาที'], NOVEL_MAX_RPM: ['Requests per minute', 'คำขอต่อนาที'],
  NOVEL_FILTER_EXTRACTOR_ENTITIES: ['Filter known entities (true / false)', 'กรองตัวละครและคำศัพท์ที่รู้จัก (true / false)'],
  NOVEL_POST_POLISH_RECONCILIATION: ['Reconcile final terms (true / false)', 'ตรวจสอบคำศัพท์หลังปรับสำนวน (true / false)'],
  NOVEL_RAG_EMBEDDING_MODEL: ['Google embedding model', 'โมเดลค้นหาความหมายของ Google'], NOVEL_RAG_RERANKER_MODEL: ['Lore ranking model', 'โมเดลจัดลำดับข้อมูลเรื่องราว'],
  NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING: ['Online learning (true / false)', 'เรียนรู้ระหว่างแปล (true / false)'],
  NOVEL_PROCEDURAL_LEARNING_CADENCE: ['Learning schedule (arc / interval / both)', 'ช่วงการเรียนรู้ (arc / interval / both)'],
  NOVEL_PROCEDURAL_LEARNING_INTERVAL: ['Chapters between learning', 'จำนวนบทก่อนเรียนรู้แต่ละครั้ง'],
  NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES: ['Issues before learning', 'จำนวนปัญหาก่อนเรียนรู้'],
  NOVEL_PROCEDURAL_REFINER_MODEL: ['Learning model', 'โมเดลสำหรับการเรียนรู้'],
};

function initialDraft(snapshot: SetupSnapshot): SetupCandidate {
  const values = { ...snapshot.values };
  if (!snapshot.existing && !snapshot.completed) {
    routeKeys.forEach(key => { values[key] = ''; });
    values.NOVEL_MAX_REVIEW_LOOPS = '3'; values.NOVEL_QUALITY_THRESHOLD = '8.5';
  }
  // Never restore credentials or arbitrary objects from session storage.
  let saved: Partial<SetupCandidate> = {};
  try {
    const parsed = JSON.parse(sessionStorage.getItem('nousetsu_setup_draft') || '{}');
    if (parsed.revision === snapshot.revision) saved = parsed;
  } catch { /* A corrupt draft is discarded. */ }
  for (const [key, value] of Object.entries(saved.values || {})) {
    if (snapshot.fields.includes(key) && typeof value === 'string') values[key] = value;
  }
  return {
    locale: saved.locale === 'en' || saved.locale === 'th' ? saved.locale : snapshot.locale, provider: saved.provider && saved.provider in providerLabels ? saved.provider : snapshot.provider,
    model: typeof saved.model === 'string' ? saved.model : snapshot.existing ? snapshot.model : '',
    skip_ai: saved.skip_ai === true, route_all: saved.route_all === true || !snapshot.existing,
    values, api_keys: {},
  };
}

export function SetupView({ initial, onExit }: { initial?: SetupSnapshot | null; onExit: (action: 'create' | 'open' | 'explore') => void }) {
  const [snapshot, setSnapshot] = useState<SetupSnapshot | null>(initial || null);
  const [draft, setDraft] = useState<SetupCandidate | null>(() => initial ? initialDraft(initial) : null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState<SetupError | null>(null);
  const [notice, setNotice] = useState('');
  const [overrides, setOverrides] = useState<string[]>([]);
  const [tested, setTested] = useState(initial?.readiness === 'tested');
  const [done, setDone] = useState(false);
  const [useRecommended, setUseRecommended] = useState(!initial?.existing);
  const [catalogs, setCatalogs] = useState<Partial<Record<ModelProvider, ModelCatalogResult>>>({});
  const heading = useRef<HTMLHeadingElement>(null);
  const generation = useRef(0);
  const t = (en: string, th: string) => draft?.locale === 'th' ? th : en;
  useEffect(() => {
    if (initial) return;
    let active = true;
    setupRequest<SetupSnapshot>('').then(result => { if (active) { setSnapshot(result); setDraft(initialDraft(result)); setTested(result.readiness === 'tested'); } })
      .catch(() => { if (active) setError(new SetupError('Could not load setup. Check that NouSetsu is running.', 'load')); });
    return () => { active = false; };
  }, [initial]);
  useEffect(() => { heading.current?.focus(); }, [step, done]);
  useEffect(() => {
    if (!draft || !snapshot || done) return;
    // Only supported nonsecret fields survive refresh. Never serialize api_keys.
    const secrets = Object.values(draft.api_keys).filter(Boolean);
    const safe = (value: string) => secrets.some(key => value.includes(key)) ? '' : value;
    try { sessionStorage.setItem('nousetsu_setup_draft', JSON.stringify({
      revision: snapshot.revision, locale: draft.locale, provider: draft.provider,
      model: safe(draft.model), skip_ai: draft.skip_ai, route_all: draft.route_all,
      values: Object.fromEntries(Object.entries(draft.values).map(([key, value]) => [key, safe(value)])),
    })); } catch { /* Setup also works without browser storage. */ }
  }, [draft, snapshot, done]);
  if (!draft || !snapshot) return <div className="setup-shell"><p role="status">{error?.message || 'Loading setup… / กำลังโหลดการตั้งค่า…'}</p><button onClick={() => window.location.reload()}>Retry / ลองอีกครั้ง</button></div>;

  const update = (change: Partial<SetupCandidate>) => {
    generation.current++;
    setDraft(current => current ? { ...current, ...change } : current);
    const aiChanged = change.provider !== undefined || change.model !== undefined || change.api_keys !== undefined || change.skip_ai !== undefined || (change.values && Object.entries(change.values).some(([key, value]) => draft.values[key] !== value && (routeKeys.includes(key) || key.includes('THINKING') || key.includes('TEMPERATURE') || key.includes('INTERACTIONS') || key === 'CUSTOM_API_BASE_URL')));
    if (aiChanged) setTested(false);
    setError(null); setNotice('');
  };
  const valueChange = (key: string, value: string) => {
    if (key === 'NOVEL_MAX_REVIEW_LOOPS' || key === 'NOVEL_QUALITY_THRESHOLD') setUseRecommended(false);
    update({ values: { ...draft.values, [key]: value } });
  };
  const currentKey = keyNames[draft.provider];
  const hasKey = Boolean(draft.api_keys[currentKey]?.trim() || snapshot.providers[draft.provider]);
  const route = draft.provider === 'gemini' ? draft.model : `${draft.provider}:${draft.model}`;
  const changeProvider = (provider: ModelProvider) => {
    const values = { ...draft.values }; routeKeys.forEach(key => { values[key] = ''; });
    update({ provider, model: '', skip_ai: false, route_all: true, values });
  };
  const messages: Record<string, string> = {
    key_rejected: t('This key was rejected. Check it or create another key.', 'คีย์นี้ถูกปฏิเสธ ตรวจสอบคีย์หรือสร้างคีย์ใหม่'),
    quota: t('Your service limit was reached. Check your account or try again later.', 'ถึงขีดจำกัดบริการแล้ว ตรวจสอบบัญชีหรือลองอีกครั้งภายหลัง'),
    model_unavailable: t('This model is unavailable. Choose another model.', 'โมเดลนี้ไม่พร้อมใช้งาน กรุณาเลือกโมเดลอื่น'),
    connection_failed: t('Could not connect. Check your connection, service address and model.', 'เชื่อมต่อไม่ได้ ตรวจสอบอินเทอร์เน็ต ที่อยู่บริการ และโมเดล'),
    conflict: t('Settings changed elsewhere. Your draft is safe; reload saved settings before retrying.', 'มีการเปลี่ยนค่าจากที่อื่น แบบร่างยังอยู่ กรุณาโหลดค่าที่บันทึกใหม่ก่อนลองอีกครั้ง'),
    completion_write_failed: t('Settings saved, but completion could not be recorded. Retry Finish setup.', 'บันทึกค่าแล้ว แต่บันทึกสถานะไม่สำเร็จ กดบันทึกการตั้งค่าอีกครั้ง'),
  };
  const report = (failure: unknown) => setError(failure instanceof SetupError ? failure : new SetupError('Could not complete this action.', 'connection_failed'));
  const check = async (kind: 'local' | 'catalog' | 'connection' | 'folder', provider = draft.provider) => {
    setBusy(true); setError(null); const requestId = generation.current;
    try {
      const candidate = provider === draft.provider ? draft : { ...draft, provider, model: '', route_all: false };
      const result = await setupRequest<{ success: boolean; models?: string[]; path?: string | null; overridden_fields?: string[] }>('/check', { kind, candidate });
      if (requestId !== generation.current) return false;
      if (kind === 'catalog') {
        setCatalogs(current => ({ ...current, [provider]: { provider, configured: true, models: result.models || [] } }));
        if (!draft.model && provider === 'gemini' && result.models?.includes('gemini-3.1-flash-lite')) update({ model: 'gemini-3.1-flash-lite' });
      }
      if (kind === 'connection') setTested(true);
      if (kind === 'folder' && result.path) valueChange('NOVEL_PROJECTS_DIR', result.path);
      if (kind === 'local') { setOverrides(result.overridden_fields || []); setNotice(t('✓ This folder is ready.', '✓ โฟลเดอร์นี้พร้อมใช้งาน')); }
      return true;
    } catch (failure) { if (requestId === generation.current) report(failure); return false; }
    finally { setBusy(false); }
  };
  const chooseFolder = async () => {
    if (!isTauriDesktopRuntime()) { await check('folder'); return; }
    try {
      const selected = await open({ directory: true, multiple: false, defaultPath: draft.values.NOVEL_PROJECTS_DIR });
      if (typeof selected === 'string') valueChange('NOVEL_PROJECTS_DIR', selected);
    } catch (failure) { report(failure); }
  };
  const next = async () => {
    if (step === 1 && !draft.skip_ai && (!hasKey || !draft.model.trim())) {
      setError(new SetupError(t('Add a key and choose a model, or select Set up AI later.', 'เพิ่มคีย์และเลือกโมเดล หรือเลือกตั้งค่า AI ภายหลัง'), 'invalid', 'api_key')); return;
    }
    if (step === 2 && !draft.values.TARGET_LANG?.trim()) { setError(new SetupError(t('Choose the translation language.', 'เลือกภาษาที่ต้องการแปล'), 'invalid', 'TARGET_LANG')); return; }
    if (step === 3 && !await check('local')) return;
    setError(null); setStep(step + 1);
  };
  const finish = async () => {
    setBusy(true); setError(null);
    try {
      const result = await setupRequest<{ success: boolean; settings_saved: boolean; revision: string; code?: string }>('/complete', draft, snapshot.revision);
      setSnapshot({ ...snapshot, revision: result.revision });
      if (!result.success) { setError(new SetupError('', result.code || 'completion_write_failed')); return; }
      try { sessionStorage.removeItem('nousetsu_setup_draft'); } catch { /* No storage required. */ }
      setDraft({ ...draft, api_keys: {} }); setDone(true);
    } catch (failure) { report(failure); }
    finally { setBusy(false); }
  };
  const steps = [t('Welcome', 'ยินดีต้อนรับ'), t('Connect AI', 'เชื่อมต่อ AI'), t('Translation', 'การแปล'), t('Storage', 'โฟลเดอร์'), t('Finish', 'เสร็จสิ้น')];
  const field = (key: string, label: string, type = 'text') => <label className="setup-field" key={key}>{label}<input aria-label={label} aria-invalid={error?.field === key} type={type} value={draft.values[key] || ''} onChange={event => valueChange(key, event.target.value)} />{error?.field === key && <span className="text-rose-200">{t(error.message, 'ตรวจสอบค่านี้ หรือเลือกตำแหน่งโฟลเดอร์อื่น แล้วลองอีกครั้ง')}</span>}</label>;
  const advanced = <details className="setup-advanced"><summary>{t('Advanced installation settings', 'การตั้งค่าขั้นสูงของแอป')}</summary>
    <p>{t('Blank values inherit defaults. Each novel can have its own settings.', 'เว้นว่างเพื่อใช้ค่าเริ่มต้น นิยายแต่ละเรื่องมีการตั้งค่าเฉพาะได้')}</p>
    <p>{t('Pacing limits slow local requests; they do not change your provider account limits. A shared fallback does not provide a separate quota.', 'ค่าความเร็วจำกัดคำขอในเครื่อง ไม่เปลี่ยนโควตาของบัญชี โมเดลสำรองไม่ได้เพิ่มโควตาแยก')}</p>
    {Object.entries(GLOBAL_ENV_GROUPS).filter(([id]) => !['general', 'paths'].includes(id)).map(([id, group]) => {
      const role = id.startsWith('agent_') ? id.slice(6) as GenerationRole : undefined;
      return <details key={id}><summary>{t(group.title, labelsTh[id])}</summary>
        {role ? <>
          <ModelRouteControl locale={draft.locale} label={t('AI model', 'โมเดล AI')} value={draft.values[`NOVEL_${role.toUpperCase()}_MODEL`] || ''} effectiveValue={route} onChange={value => valueChange(`NOVEL_${role.toUpperCase()}_MODEL`, value)} catalogs={catalogs} loadingCatalogs={{}} catalogErrors={{}} apiKeyStatus={Object.fromEntries(Object.entries(keyNames).map(([p, key]) => [key, Boolean(draft.api_keys[key] || snapshot.providers[p as ModelProvider])]))} customBaseUrl={draft.values.CUSTOM_API_BASE_URL} onLoadCatalog={provider => { void check('catalog', provider); }} />
          <GenerationSettingsEditor locale={draft.locale} role={role} provider={providerForRoute(draft.values[`NOVEL_${role.toUpperCase()}_MODEL`] || route)} model={modelIdForRoute(draft.values[`NOVEL_${role.toUpperCase()}_MODEL`] || route)} environmentValues={draft.values} onEnvironmentChange={valueChange} />
        </> : <>
          {group.keys.filter(key => !['NOVEL_MODEL', 'NOVEL_TEMPERATURE', 'NOVEL_THINKING_LEVEL', 'NOVEL_THINKING_BUDGET', 'NOVEL_USE_INTERACTIONS'].includes(key)).map(key => field(key, settingLabels[key] ? t(...settingLabels[key]) : GLOBAL_ENV_LABELS[key] || key))}
          {id === 'models' && <GenerationSettingsEditor locale={draft.locale} role="default" provider="all" environmentValues={draft.values} onEnvironmentChange={valueChange} />}
        </>}
      </details>;
    })}
    <details><summary>{t('Additional services and scraper paths', 'บริการเพิ่มเติมและตำแหน่งโปรแกรมนำเข้าเว็บ')}</summary>
      {field('CUSTOM_API_BASE_URL', t('Custom service address', 'ที่อยู่บริการกำหนดเอง'), 'url')}
      {field('NOVEL_SCRAPER_PATH', t('External scraper folder (optional)', 'โฟลเดอร์โปรแกรมนำเข้าเว็บภายนอก (ไม่บังคับ)'))}
      {field('NOVEL_SCRAPER_PYTHON', t('External scraper Python (optional)', 'Python ของโปรแกรมนำเข้าเว็บภายนอก (ไม่บังคับ)'))}
      {Object.entries(keyNames).map(([provider, key]) => <label key={key} className="setup-field">{providerLabels[provider as ModelProvider]}<input type="password" autoComplete="new-password" value={draft.api_keys[key] || ''} placeholder={t('Blank keeps the saved key', 'เว้นว่างเพื่อใช้คีย์เดิม')} onChange={event => update({ api_keys: { ...draft.api_keys, [key]: event.target.value } })} /></label>)}
    </details>
    <p>{t('Chunking, safety, story memory and project paths are available in Settings after creating a novel. Their recommended defaults stay enabled.', 'การแบ่งบท ความปลอดภัย ความจำเรื่องราว และโฟลเดอร์เฉพาะนิยาย ตั้งค่าได้หลังสร้างนิยาย ค่าเริ่มต้นที่แนะนำยังเปิดใช้งาน')}</p>
  </details>;
  return <main className="setup-shell" lang={draft.locale}>
    <header className="setup-header"><span className="flex items-center gap-2"><BookOpen aria-hidden="true" /> NouSetsu</span>
      <select aria-label="Language / ภาษา" value={draft.locale} disabled={busy} onChange={event => {
        const locale = event.target.value as 'en' | 'th';
        update({ locale, ...(!snapshot.existing && draft.values.TARGET_LANG === (draft.locale === 'en' ? 'English' : 'Thai') ? { values: { ...draft.values, TARGET_LANG: locale === 'th' ? 'Thai' : 'English' } } : {}) });
      }}><option value="en">English</option><option value="th">ไทย</option></select>
    </header>
    {!done && <nav aria-label={t('Setup progress', 'ขั้นตอนการตั้งค่า')}><ol className="setup-progress">{steps.map((label, index) => <li key={index} aria-current={index === step ? 'step' : undefined}><span>{index < step ? '✓' : index + 1}</span><span>{label}</span></li>)}</ol><p className="setup-step-count">{t(`Step ${step + 1} of 5`, `ขั้นตอนที่ ${step + 1} จาก 5`)}</p></nav>}
    <section className="setup-card">
      <h1 tabIndex={-1} ref={heading}>{done ? t('You’re ready to begin', 'พร้อมเริ่มใช้งานแล้ว') : [t('Let’s get NouSetsu ready', 'ตั้งค่า NouSetsu ให้พร้อมใช้งาน'), t('Connect your AI service', 'เชื่อมต่อบริการ AI'), t('Your translation defaults', 'ค่าเริ่มต้นสำหรับการแปล'), t('Save your novels', 'โฟลเดอร์เก็บนิยาย'), t('Review your setup', 'ตรวจสอบการตั้งค่า')][step]}</h1>
      {done ? <div className="space-y-4"><p>{draft.skip_ai ? t('You can import and read novels now. Connect AI when you are ready to translate.', 'นำเข้าและอ่านนิยายได้ทันที เชื่อมต่อ AI เมื่อพร้อมแปล') : t('Your settings are saved. Choose where to begin.', 'บันทึกการตั้งค่าแล้ว เลือกขั้นตอนถัดไป')}</p>
        <button className="setup-primary" onClick={() => onExit('create')}>{t('Create my first novel', 'สร้างนิยายเรื่องแรก')} <ArrowRight aria-hidden="true" /></button>
        <button onClick={() => onExit('open')}>{t('Open an existing novel', 'เปิดนิยายที่มีอยู่')}</button><button onClick={() => onExit('explore')}>{t('Explore Studio', 'สำรวจ Studio')}</button>
      </div> : <fieldset disabled={busy} className="space-y-5">
        {step === 0 && <><p>{t('Translate novels with consistent characters, terminology and story memory. We’ll guide you through the essentials.', 'แปลนิยายโดยรักษาชื่อตัวละคร คำศัพท์ และความต่อเนื่องของเรื่อง เราจะช่วยตั้งค่าสิ่งจำเป็นทีละขั้น')}</p>
          <p>{isTauriDesktopRuntime() ? t('Everything you need to run the app is included. No separate Python installation is needed.', 'แอปรวมสิ่งที่จำเป็นไว้แล้ว ไม่ต้องติดตั้ง Python เพิ่ม') : t('Your installed Python package runs this setup page. Node.js is not needed.', 'แพ็กเกจ Python ที่ติดตั้งเปิดหน้าตั้งค่านี้ ไม่ต้องติดตั้ง Node.js')}</p>
          <p>{t('Novels and settings stay on this computer. Text is sent to your chosen AI service during translation. You can connect later; services may charge for usage.', 'นิยายและการตั้งค่าเก็บในเครื่องนี้ เมื่อแปลจะส่งข้อความไปยังบริการ AI ที่เลือก เชื่อมต่อภายหลังได้ และบริการอาจคิดค่าการใช้งาน')}</p></>}
        {step === 1 && <><p>{t('This service translates and reviews your chapters.', 'บริการนี้ใช้แปลและตรวจสอบบทนิยาย')}</p>
          <div className="setup-providers">{Object.entries(providerLabels).map(([provider, label]) => <button key={provider} type="button" aria-pressed={draft.provider === provider} onClick={() => changeProvider(provider as ModelProvider)}>{provider === 'custom' ? t(label, 'บริการกำหนดเอง') : label}</button>)}</div>
          <label className="setup-field">{t('Connection key', 'คีย์เชื่อมต่อ')}<div className="flex gap-2"><input aria-label={t('Connection key', 'คีย์เชื่อมต่อ')} type={showKey ? 'text' : 'password'} autoComplete="new-password" value={draft.api_keys[currentKey] || ''} placeholder={snapshot.providers[draft.provider] ? t('Saved key configured—blank keeps it', 'มีคีย์ที่บันทึกไว้ เว้นว่างเพื่อใช้คีย์เดิม') : t('Paste your key here', 'วางคีย์ที่นี่')} onChange={event => update({ skip_ai: false, api_keys: { ...draft.api_keys, [currentKey]: event.target.value } })} /><button type="button" aria-pressed={showKey} onClick={() => setShowKey(!showKey)}>{showKey ? t('Hide', 'ซ่อน') : t('Show', 'แสดง')}</button></div></label>
          {snapshot.credential_sources?.[draft.provider] === 'process' && <p>{t('This key was supplied when the app started. Saving a replacement does not change that startup override; connection testing uses the effective key.', 'คีย์นี้ถูกกำหนดตอนเปิดแอป การบันทึกคีย์ใหม่ไม่แทนค่าเริ่มต้นนั้น การทดสอบใช้คีย์ที่มีผลจริง')}</p>}
          {helpLinks[draft.provider] ? <a href={helpLinks[draft.provider]} target="_blank" rel="noreferrer" onClick={event => {
            if (isTauriDesktopRuntime()) { event.preventDefault(); void invoke('plugin:shell|open', { path: helpLinks[draft.provider] }).catch(() => setError(new SetupError(t('Could not open your browser. Copy the help link address and open it there.', 'เปิดเบราว์เซอร์ไม่ได้ คัดลอกที่อยู่ลิงก์นี้แล้วเปิดในเบราว์เซอร์'), 'invalid'))); }
          }}>{t('How to get a key', 'วิธีสร้างคีย์เชื่อมต่อ')} ↗</a> : <p>{t('Get the connection key and service address from your provider.', 'ขอคีย์เชื่อมต่อและที่อยู่บริการจากผู้ให้บริการ')}</p>}
          {draft.provider === 'custom' && field('CUSTOM_API_BASE_URL', t('Service address', 'ที่อยู่บริการ'), 'url')}
          {hasKey && <><label className="setup-field">{t('AI model', 'โมเดล AI')}<input aria-label={t('AI model', 'โมเดล AI')} list="setup-models" value={draft.model} placeholder={t('Choose a model or enter its ID', 'เลือกโมเดลหรือป้อนรหัส')} onChange={event => update({ model: event.target.value, skip_ai: false })} /><datalist id="setup-models">{catalogs[draft.provider]?.models.map(model => <option key={model} value={model} />)}</datalist></label>
            {snapshot.existing && <button onClick={() => { const values = { ...draft.values }; routeKeys.forEach(key => { values[key] = ''; }); update({ route_all: true, values }); }}>{t('Use this model for all translation tasks', 'ใช้โมเดลนี้สำหรับทุกขั้นตอนการแปล')}</button>}
            <button onClick={() => { void check('catalog'); }}>{t('Load available models', 'โหลดโมเดลที่ใช้ได้')}</button><p>{t('If the list cannot load, enter your provider’s model ID manually.', 'หากโหลดรายการไม่ได้ ให้ป้อนรหัสโมเดลจากผู้ให้บริการ')}</p>
            <button disabled={!draft.model} onClick={() => { void check('connection'); }}>{t('Test connection', 'ทดสอบการเชื่อมต่อ')}</button><p>{t('A small sample will be sent to this service. Your provider may charge for the test.', 'จะส่งตัวอย่างสั้น ๆ ไปยังบริการนี้ ผู้ให้บริการอาจคิดค่าบริการทดสอบ')}</p><p>{t('This checks the drafting model. Additional models in Advanced are not individually tested.', 'ทดสอบโมเดลร่างคำแปล โมเดลเพิ่มเติมในหัวข้อขั้นสูงไม่ได้ทดสอบแยก')}</p>
          </>}
          <p role="status" className="flex gap-2">{tested ? <CheckCircle2 aria-hidden="true" /> : <AlertCircle aria-hidden="true" />}{tested ? t('Connection tested successfully', 'ทดสอบการเชื่อมต่อสำเร็จ') : error || (snapshot.readiness === 'needs_attention' && !draft.route_all) ? t('Needs attention—review the key and model routes', 'ต้องตรวจสอบคีย์และการเลือกโมเดล') : hasKey && draft.model ? t('Configured—untested', 'ตั้งค่าแล้ว ยังไม่ได้ทดสอบ') : t('Not connected', 'ยังไม่เชื่อมต่อ')}</p>
          <button onClick={() => { update({ skip_ai: true }); setStep(2); }}>{t('Set up AI later', 'ตั้งค่า AI ภายหลัง')}</button>
          <p>{snapshot.providers.gemini || draft.api_keys.GEMINI_API_KEY ? t('Semantic story retrieval is available with Google credentials.', 'ค้นหาความหมายของเรื่องราวได้เมื่อมีคีย์ Google') : t('Story memory uses keyword search. Semantic search additionally needs a Google key.', 'ความจำเรื่องราวใช้การค้นหาคำศัพท์ การค้นหาความหมายต้องใช้คีย์ Google เพิ่ม')}</p>
        </>}
        {step === 2 && <><p>{t('Each novel can override these choices.', 'นิยายแต่ละเรื่องสามารถเปลี่ยนค่าเหล่านี้ได้')}</p>
          <label className="setup-field">{t('Original language', 'ภาษาต้นฉบับ')}<select value={draft.values.SOURCE_LANG} onChange={event => valueChange('SOURCE_LANG', event.target.value)}><option value="auto">{t('Detect automatically', 'ตรวจจับอัตโนมัติ')}</option>{Array.from(new Set(['Japanese', 'Chinese', 'Korean', 'English', 'Thai', draft.values.SOURCE_LANG])).filter(language => language && language !== 'auto').map(language => <option key={language}>{language}</option>)}</select></label>
          <label className="setup-field">{t('Translate into', 'แปลเป็นภาษา')}<input aria-label={t('Translate into', 'แปลเป็นภาษา')} value={draft.values.TARGET_LANG} list="setup-languages" onChange={event => valueChange('TARGET_LANG', event.target.value)} /><datalist id="setup-languages">{['English', 'Thai', 'Japanese', 'Chinese', 'Korean', 'French', 'Spanish', 'German', 'Vietnamese', 'Indonesian'].map(language => <option key={language}>{language}</option>)}</datalist></label>
          <label className="flex gap-3 items-center"><input type="checkbox" checked={useRecommended} onChange={event => { setUseRecommended(event.target.checked); if (event.target.checked) update({ values: { ...draft.values, NOVEL_MAX_REVIEW_LOOPS: '3', NOVEL_QUALITY_THRESHOLD: '8.5' } }); else { document.querySelector<HTMLDetailsElement>('.setup-advanced')?.setAttribute('open', ''); } }} />{t('Use recommended quality settings', 'ใช้ค่าคุณภาพที่แนะนำ')}</label>
          <p>{t('Recommended: three review passes, quality target 8.5. Long chapters and story continuity are handled automatically.', 'ค่าแนะนำ: ตรวจสอบสูงสุด 3 รอบ เป้าหมายคุณภาพ 8.5 แอปจัดการบทยาวและความต่อเนื่องอัตโนมัติ')}</p>{advanced}</>}
        {step === 3 && <><p>{t('Choose an easy-to-find folder for your novels and translations.', 'เลือกโฟลเดอร์ที่หาได้ง่ายสำหรับนิยายและคำแปล')}</p>{field('NOVEL_PROJECTS_DIR', t('Novel folder', 'โฟลเดอร์นิยาย'))}
          <div className="flex flex-wrap gap-3"><button onClick={() => { void chooseFolder(); }}><FolderOpen aria-hidden="true" />{t('Choose folder', 'เลือกโฟลเดอร์')}</button><button onClick={() => { void check('local'); }}>{t('Check folder', 'ตรวจสอบโฟลเดอร์')}</button></div>
          <p>{t('Changing this folder does not move existing novels. If a folder picker is unavailable, paste a folder path above.', 'เปลี่ยนโฟลเดอร์นี้จะไม่ย้ายนิยายเดิม หากเลือกโฟลเดอร์ไม่ได้ ให้วางตำแหน่งโฟลเดอร์ด้านบน')}</p><p role="status">{notice}</p></>}
        {step === 4 && <><p>{t('Check these choices before saving. You can change them later in Settings.', 'ตรวจสอบค่าก่อนบันทึก เปลี่ยนได้ภายหลังในหน้าการตั้งค่า')}</p>
          {[[t('AI service', 'บริการ AI'), draft.skip_ai ? t('Connect later', 'เชื่อมต่อภายหลัง') : `${providerLabels[draft.provider]} · ${draft.model}`, 1], [t('Translation languages', 'ภาษาสำหรับแปล'), `${draft.values.SOURCE_LANG} → ${draft.values.TARGET_LANG}`, 2], [t('Quality', 'คุณภาพ'), `${draft.values.NOVEL_MAX_REVIEW_LOOPS || '3'} / ${draft.values.NOVEL_QUALITY_THRESHOLD || '8.5'}`, 2], [t('Novel folder', 'โฟลเดอร์นิยาย'), draft.values.NOVEL_PROJECTS_DIR, 3]].map(([label, value, destination]) => <div key={label} className="setup-summary"><div><h2>{label}</h2><p>{value}</p></div><button onClick={() => setStep(Number(destination))}>{t('Edit', 'แก้ไข')}</button></div>)}
          <p>{t('Connection keys are saved locally and never shown in this summary.', 'คีย์เชื่อมต่อจะบันทึกในเครื่อง และไม่แสดงในสรุปนี้')}</p>
        </>}
      </fieldset>}
      {overrides.length > 0 && <aside role="status" className="mt-5 text-amber-200"><p>{t('Some settings are controlled outside this app. Saved changes will not override them until the startup settings change.', 'บางค่าถูกกำหนดจากภายนอกแอป ค่าที่บันทึกจะไม่แทนค่าเหล่านั้นจนกว่าจะเปลี่ยนค่าตอนเปิดแอป')}</p><p>{overrides.join(', ')}</p></aside>}
      {error && <div role="alert" className="setup-error"><AlertCircle aria-hidden="true" /><div>{messages[error.code] || (draft.locale === 'th' ? 'ตรวจสอบค่าที่ป้อน คีย์ โมเดล และสิทธิ์ของโฟลเดอร์ แล้วลองอีกครั้ง' : error.message)}{error.field && <p>{error.field}</p>}{error.code === 'conflict' && <button onClick={async () => { try { const refreshed = await setupRequest<SetupSnapshot>(''); setSnapshot(refreshed); setError(null); } catch (failure) { report(failure); } }}>{t('Reload saved settings; keep my draft', 'โหลดค่าที่บันทึก โดยเก็บแบบร่างไว้')}</button>}</div></div>}
      {!done && <footer className="setup-footer"><button disabled={busy || step === 0} onClick={() => { setError(null); setStep(step - 1); }}>{t('Back', 'ย้อนกลับ')}</button><button className="setup-primary" disabled={busy} onClick={() => { void (step === 4 ? finish() : next()); }}>{busy ? t('Please wait…', 'โปรดรอสักครู่…') : step === 4 ? t('Finish setup', 'บันทึกการตั้งค่า') : t('Continue', 'ถัดไป')}<ArrowRight aria-hidden="true" /></button></footer>}
    </section>
  </main>;
}
