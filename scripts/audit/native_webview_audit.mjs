// Real Tauri WebView2 browser automation. No computer-use or mocked Tauri bridge.
import { chromium, expect } from '../../web/node_modules/playwright/test.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = path.join(root, 'audit-results/settings');
const mode = process.argv[2] || 'release';
if (!['dev', 'release'].includes(mode)) throw new Error('Expected dev or release');
const project = path.join(root, `src-tauri/target/settings-audit/native-${mode}/projects/Native A`);
const observations = [];
const resultFile = path.join(evidence, `native-${mode}-cdp-results.json`);
const roles = [['extractor','Entity Extractor'],['drafter','Context-Aware Drafter'],['critic','Critique Agent'],['polisher','Polishing Agent'],['chronicler','Chronicler Agent'],['scraper','Novel Scraper']];
const base = 'http://127.0.0.1:15474';
const saveEvidence = () => fs.writeFileSync(resultFile, JSON.stringify({ mode, tool: 'Playwright CDP attached to actual Tauri WebView2', project_path: project, observations }, null, 2));
function record(caseName, ids, actual, expected = actual) {
  observations.push({case:caseName, setting_ids:ids, status:JSON.stringify(actual) === JSON.stringify(expected) ? 'pass' : 'fail', actual, expected});
  saveEvidence();
}
async function api(endpoint, body, method) {
  const response = await fetch(base + endpoint, {method:method || (body ? 'POST':'GET'), headers:{'Content-Type':'application/json'}, body:body ? JSON.stringify(body) : undefined});
  if (!response.ok) throw new Error(`${endpoint} HTTP ${response.status}: ${(await response.text()).slice(0,200)}`);
  return response.json();
}
const configEndpoint = '/api/settings?' + new URLSearchParams({project_path:project});
function diskYaml() {
  return JSON.parse(execFileSync('uv', ['run','--no-sync','python','-c', 'import json,sys,yaml; from pathlib import Path; print(json.dumps(yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))))', path.join(project,'.novel/config.yaml')], {cwd:root, encoding:'utf8', windowsHide:true}));
}
let browser;
try {
  saveEvidence();
  for(let i=0;i<100;i++) {
    try { browser=await chromium.connectOverCDP('http://127.0.0.1:5195'); break; }
    catch { await new Promise(resolve=>setTimeout(resolve,500)); }
  }
  if (!browser) throw new Error('Owned WebView2 did not expose its debugging port');
  let page;
  for(let i=0;i<100;i++) {
    page=browser.contexts().flatMap(context=>context.pages()).find(p=>p.url().includes(mode==='release' ? ':15474' : ':5187'));
    if(page)break;
    await new Promise(resolve=>setTimeout(resolve,300));
  }
  if (!page) throw new Error('Actual audit WebView page was not found; refusing other browser targets');
  page.setDefaultTimeout(15000);
  const native=await page.evaluate(()=>('__TAURI_INTERNALS__' in window)||('__TAURI__' in window));
  if (!native) throw new Error('No real Tauri runtime bridge detected');
  const environment=await api('/api/environment');
  const envPath=environment.env_file_path;
  if (!(envPath.includes('com.nousetsu.settingsaudit') || envPath.includes('settings-audit\\workspace'))) throw new Error('Settings file is not audit-owned');
  record('Actual Tauri runtime and isolated settings path',[],{native:true,env_file_path:envPath,url:page.url()});
  const open=async section=>{await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/settings?'+new URLSearchParams({project,section})); await expect(page.getByRole('button',{name:section==='global'?'Save Global Settings':'Save Settings',exact:true})).toBeVisible();};
  const field=(scope,label)=>scope.locator('label').filter({hasText:label}).first().locator('xpath=..').locator('input, select').first();
  const generation=async(card,temp,budget)=>{await card.getByLabel('Gemini Interactions API',{exact:true}).selectOption('false'); await card.getByLabel('Temperature',{exact:true}).fill(temp); await card.getByRole('combobox',{name:'Thinking level',exact:true}).selectOption('low'); await card.getByLabel('Thinking budget',{exact:true}).fill(budget);};
  const save=async global=>{const endpoint=global?'/api/environment':'/api/settings'; const put=page.waitForResponse(r=>r.url().includes(endpoint)&&r.request().method()==='PUT'); const get=page.waitForResponse(r=>r.url().includes(endpoint)&&r.request().method()==='GET'); await page.getByRole('button',{name:global?'Save Global Settings':'Save Settings',exact:true}).click(); expect((await put).status()).toBe(200); await get;};
  await open('all');
  const form=page.locator('form');
  const values={title:[`CDP ${mode} 日本`,/^Novel Title$/],genre:['fantasy',/^Genre$/],source_language:['Japanese',/^Source Language$/],target_language:['English',/^Target Language$/],project_id:[`audit-${mode}`,/^Project Identifier$/],chunk_threshold_lines:['900',/^Chunk Threshold/],target_chunk_lines:['450',/^Chunk Size/],chunk_overlap_lines:['5',/^Chunk Overlap/],rag_top_k:['4',/^Lore Retrieval Top-K/],rag_embedding_model:['mock-embedding',/^Dense Embedding Model$/],rag_reranker_model:['mock-reranker',/^Cross-Encoder Reranker Model$/],safety_subdivision_min_lines:['10',/^Subdivision Min Lines/],safety_subdivision_max_depth:['5',/^Subdivision Max/],max_tpm:['50000',/^Max Tokens Per Minute/],max_rpm:['80',/^Max Requests Per Minute/],raw_dir:['raw cdp 日本',/^Raw Chapters Directory$/],output_dir:['translated cdp ไทย',/^Translated Chapters Directory$/],max_review_loops:['2',/^Max Review Loops/],quality_threshold:['9',/^Quality Score Threshold/]};
  for(const [value,label] of Object.values(values)) await field(form,label).fill(value);
  const models={model_name:'mock-cdp-primary',fallback_model:'mock-cdp-fallback'};
  await form.getByLabel('Primary model route model ID',{exact:true}).fill(models.model_name);
  await form.getByLabel('Shared fallback route model ID',{exact:true}).fill(models.fallback_model);
  for(const [i,[role,title]] of roles.entries()) {models[role+'_model']='mock-cdp-'+role; const model=form.getByLabel(title+' model model ID',{exact:true}); await model.fill(models[role+'_model']); await generation(model.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]'),(0.3+i*.1).toFixed(1),String(100+i));}
  const toggles={enable_patch_polishing:'Enable Diff/Patch Polishing Engine',enable_chunking:'Chunking Enabled',auto_update_bible:'Auto-Update Novel Bible',cross_folder_summaries:'Cross-Folder Multi-Volume Memory',filter_scene_characters:'Scene Character Filtering',filter_extractor_entities:'Extractor Known Entity Filtering',enable_post_polish_reconciliation:'Post-Polish Term Reconciliation',enable_rag:'Hybrid RAG Enabled',enable_rag_reranker:'Enable Cross-Encoder Reranker',safety_recursive_subdivision:'Subdivision Enabled'};
  for(const label of Object.values(toggles)){const toggle=form.getByText(label,{exact:true}).locator('xpath=ancestor::*[.//button[@role="switch"]][1]').getByRole('switch'); if(await toggle.getAttribute('aria-checked')==='true')await toggle.click();}
  await save(false);
  const cfg=await api(configEndpoint);
  const disk=diskYaml();
  for(const [key,[expected]] of Object.entries(values)){expect(String(cfg.config[key])).toBe(expected);expect(String(disk[key])).toBe(expected);record('Native project control persisted',['project.'+key],String(disk[key]),expected);}
  for(const [key,value] of Object.entries(models)){expect(disk[key]).toBe(value);record('Native model route persisted',['project.'+key],disk[key],value);}
  for(const key of Object.keys(toggles)){expect(disk[key]).toBe(false);record('Native switch persisted',['project.'+key],disk[key],false);}
  for(const [i,[role]] of roles.entries()){const expected={temperature:Number((.3+i*.1).toFixed(1)),thinking_level:'low',thinking_budget:100+i,use_interactions_api:false};expect(disk.generation_settings[role]).toEqual(expected);record('Native role generation persisted',Object.keys(expected).map(k=>`project.generation_settings.${role}.${k}`),disk.generation_settings[role],expected);}
  await page.reload(); await expect(field(page.locator('form'),/^Novel Title$/)).toHaveValue(values.title[0]);
  for(const [value,label] of Object.values(values)) await expect(field(page.locator('form'),label)).toHaveValue(value);
  await page.screenshot({path:path.join(evidence,`native-${mode}-project.png`),fullPage:true});
  await open('global');
  const globals={};
  const simple=[['Language Defaults','SOURCE_LANG','Japanese'],['Language Defaults','TARGET_LANG','English'],['Quality Defaults','NOVEL_MAX_REVIEW_LOOPS','1'],['Quality Defaults','NOVEL_QUALITY_THRESHOLD','9'],['Memory & Entity Defaults','NOVEL_FILTER_EXTRACTOR_ENTITIES','false'],['Memory & Entity Defaults','NOVEL_POST_POLISH_RECONCILIATION','false'],['RAG Model Defaults','NOVEL_RAG_EMBEDDING_MODEL','mock-global-embedding'],['RAG Model Defaults','NOVEL_RAG_RERANKER_MODEL','mock-global-reranker'],['Rate Limit Defaults','NOVEL_MAX_TPM','45000'],['Rate Limit Defaults','NOVEL_MAX_RPM','70'],['Workspace Defaults','NOVEL_PROJECTS_DIR',path.dirname(project)],['Workspace Defaults','NOVEL_SCRAPER_PATH',path.join(path.dirname(project),'scraper')],['Workspace Defaults','NOVEL_SCRAPER_PYTHON',path.join(path.dirname(project),'python.exe')]];
  for(const [group,key,value] of simple){await page.getByRole('textbox',{name:group+' '+key,exact:true}).fill(value);globals[key]=value;}
  for(const [key,label] of [['DEFAULT_MODEL','Default model'],['NOVEL_MODEL','Primary model'],['NOVEL_FALLBACK_MODEL','Shared fallback model']]) {globals[key]='mock-cdp-global-'+key.toLowerCase();await page.getByLabel(label+' model ID',{exact:true}).fill(globals[key]);}
  await generation(page.getByRole('heading',{name:'Shared generation defaults',exact:true}).locator('xpath=..'),'0.4','101'); Object.assign(globals,{NOVEL_TEMPERATURE:'0.4',NOVEL_THINKING_LEVEL:'low',NOVEL_THINKING_BUDGET:'101',NOVEL_USE_INTERACTIONS:'false'});
  for(const [i,[role,title]] of roles.entries()){const card=page.getByRole('heading',{name:title,exact:true}).locator('xpath=ancestor::section[1]');const prefix='NOVEL_'+role.toUpperCase();globals[prefix+'_MODEL']='mock-cdp-global-'+role;await card.getByLabel('Model route model ID',{exact:true}).fill(globals[prefix+'_MODEL']);await generation(card,'0.5',String(200+i));Object.assign(globals,{[prefix+'_TEMPERATURE']:'0.5',[prefix+'_THINKING_LEVEL']:'low',[prefix+'_THINKING_BUDGET']:String(200+i),[prefix+'_USE_INTERACTIONS']:'false'});}
  globals.CUSTOM_API_BASE_URL='http://127.0.0.1:5193/v1';await page.getByLabel('Custom OpenAI-compatible base URL',{exact:true}).fill(globals.CUSTOM_API_BASE_URL);
  const secrets=['GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY','CUSTOM_API_KEY'];
  for(const key of secrets) await page.locator('#api-key-'+key).fill('synthetic-cdp-'+key);
  await save(true);
  const global=await api('/api/environment');expect(JSON.stringify(global)).not.toContain('synthetic-cdp-');
  const diskGlobals=JSON.parse(execFileSync('uv',['run','--no-sync','python','-c','import json,sys; from dotenv import dotenv_values; values=dotenv_values(sys.argv[1]); print(json.dumps({k:values.get(k) for k in json.loads(sys.argv[2])}))',envPath,JSON.stringify(Object.keys(globals))],{cwd:root,encoding:'utf8',windowsHide:true}));
  for(const [key,value] of Object.entries(globals)){expect(global.values[key]).toBe(value);expect(diskGlobals[key]).toBe(value);record('Native global input persisted',['env.'+key],global.values[key],value);}
  for(const key of secrets){expect(global.api_key_status[key]).toBe(true);record('Native synthetic key saved and response redacted',['env.'+key],true,true);}
  await page.reload(); await expect(page.locator('#api-key-GEMINI_API_KEY')).toHaveValue('');
  await save(true);for(const key of secrets)expect((await api('/api/environment')).api_key_status[key]).toBe(true);
  for(const key of secrets) await page.locator('#api-key-'+key).locator('xpath=..').getByRole('button',{name:'Clear saved key',exact:true}).click();
  await save(true);for(const key of secrets)expect((await api('/api/environment')).api_key_status[key]).toBe(false);
  record('Native blank key preservation and explicit clear',secrets.map(k=>'env.'+k),true,true);
  await page.screenshot({path:path.join(evidence,`native-${mode}-global.png`),fullPage:true});
  const raw=path.join(project,values.raw_dir[0]);fs.mkdirSync(raw,{recursive:true});
  const chapter=1+Math.max(0,...fs.readdirSync(raw).filter(n=>/^\d+\.txt$/.test(n)).map(n=>Number(n.replace('.txt',''))));
  const source=path.join(raw,String(chapter).padStart(4,'0')+'.txt');
  fs.writeFileSync(source,'第一章\n太郎は家に帰った。\n旅人は歩き始めた。','utf8');
  await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/studio?'+new URLSearchParams({project,folder:values.raw_dir[0]}));
  await expect(page.getByRole('button',{name:'Translate Batch',exact:true})).toBeVisible();
  const started=page.waitForResponse(r=>r.url().endsWith('/api/translate/start'));await page.getByRole('button',{name:'Translate Batch',exact:true}).click();expect((await started).status()).toBe(200);
  for(let i=0;i<160;i++){if(!(await api('/api/translate/status')).is_running)break;await new Promise(resolve=>setTimeout(resolve,500));}
  const metadata=JSON.parse(fs.readFileSync(path.join(project,'.novel/metadata.json'),'utf8'));
  const completed=Object.values(metadata.chapters).filter(c=>c.checkpoint?.status==='completed'&&path.resolve(c.source_file)===path.resolve(source));expect(completed.length).toBeGreaterThan(0);
  for(const item of completed)expect(fs.existsSync(item.output_file)).toBe(true);
  record('Native UI-started fresh mock translation completes',[],{completed:completed.length,chapter,source_file:path.basename(source),models:[...new Set(completed.map(c=>c.model))]});
  console.log(JSON.stringify({mode,setting_ids:new Set(observations.flatMap(r=>r.setting_ids)).size,observations:observations.length,completed:true}));
} catch(error) {
  observations.push({case:'Native browser audit interrupted',setting_ids:[],status:'blocked',reason:String(error)});saveEvidence();console.error(String(error));process.exitCode=1;
} finally {
  if(browser) await browser.close();
}
