// Real Tauri WebView2 browser automation. No computer-use or mocked Tauri bridge.
import { chromium, expect } from '../../web/node_modules/playwright/test.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const evidence = path.join(root, 'audit-results/settings-repair');
const mode = process.argv[2] || 'release';
if (!['dev', 'release'].includes(mode)) throw new Error('Expected dev or release');
const project = path.join(root, `src-tauri/target/settings-repair/native-${mode}/projects/Native A`);
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
  const headers={'Content-Type':'application/json'};
  if(method==='PUT')headers['If-Match']=`"${(await api(endpoint)).revision}"`;
  const response = await fetch(base + endpoint, {method:method || (body ? 'POST':'GET'), headers, body:body ? JSON.stringify(body) : undefined});
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
  const backendContext=await api('/api/desktop-info');
  expect(backendContext.mode).toBe(mode==='release'?'frozen':'source');
  const envPath=environment.env_file_path;
  if (!(envPath.includes('com.nousetsu.settingsrepair') || envPath.includes('settings-repair\\workspace'))) throw new Error('Settings file is not audit-owned');
  record('Actual Tauri runtime and isolated settings path',[],{native:true,env_file_path:envPath,url:page.url(),backend_context:backendContext});
  const open=async section=>{await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/settings?'+new URLSearchParams({project,section})); await expect(page.getByRole('button',{name:section==='global'?'Save Global Settings':'Save Settings',exact:true})).toBeVisible();};
  const field=(scope,label)=>scope.getByLabel(label).first();
  const generation=async(card,temp,budget)=>{await card.getByLabel('Gemini Interactions API',{exact:true}).selectOption('false'); await card.getByLabel('Temperature',{exact:true}).fill(temp); await card.getByRole('combobox',{name:'Thinking level',exact:true}).selectOption('low'); await card.getByLabel('Thinking budget',{exact:true}).fill(budget);};
  const save=async global=>{const endpoint=global?'/api/environment':'/api/settings'; const put=page.waitForResponse(r=>r.url().includes(endpoint)&&r.request().method()==='PUT'); await page.getByRole('button',{name:global?'Save Global Settings':'Save Settings',exact:true}).click(); expect((await put).status()).toBe(200); await expect(page.getByRole('button',{name:global?'Save Global Settings':'Save Settings',exact:true})).toBeEnabled();};
  await open('all');
  const form=page.locator('form');
  const values={title:[`CDP ${mode} 日本`,/^Novel Title$/],genre:['fantasy',/^Genre$/],source_language:['Japanese',/^Source Language$/],target_language:['English',/^Target Language$/],project_id:[`audit-${mode}`,/^Project Identifier$/],chunk_threshold_lines:['900',/^Chunk Threshold/],target_chunk_lines:['450',/^Chunk Size/],chunk_overlap_lines:['5',/^Chunk Overlap/],rag_top_k:['4',/^Lore Retrieval Top-K/],rag_embedding_model:['mock-embedding',/^Dense Embedding Model$/],rag_reranker_model:['mock-reranker',/^Cross-Encoder Reranker Model$/],safety_subdivision_min_lines:['10',/^Subdivision Min Lines/],safety_subdivision_max_depth:['5',/^Subdivision Max/],max_tpm:['50000',/^Max Tokens Per Minute/],max_rpm:['80',/^Max Requests Per Minute/],raw_dir:['raw cdp 日本',/^Raw Chapters Directory$/],output_dir:['translated cdp ไทย',/^Translated Chapters Directory$/],max_review_loops:['2',/^Max Review Loops/],quality_threshold:['9',/^Quality Score Threshold/],procedural_learning_interval:['20',/^procedural_learning_interval$/],procedural_learning_min_failures:['3',/^procedural_learning_min_failures$/],procedural_refiner_model:['mock-refiner',/^Refiner model$/]};
  for(const [value,label] of Object.values(values)) await field(form,label).fill(value);
  const models={model_name:'mock-cdp-primary',fallback_model:'mock-cdp-fallback'};
  await form.getByLabel('Primary model route model ID',{exact:true}).fill(models.model_name);
  await form.getByLabel('Shared fallback route model ID',{exact:true}).fill(models.fallback_model);
  for(const [i,[role,title]] of roles.entries()) {models[role+'_model']='mock-cdp-'+role; const model=form.getByLabel(title+' model model ID',{exact:true}); await model.fill(models[role+'_model']); await generation(model.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]'),(0.3+i*.1).toFixed(1),String(100+i));}
  const toggles={enable_patch_polishing:'Enable Diff/Patch Polishing Engine',enable_chunking:'Chunking Enabled',auto_update_bible:'Auto-Update Novel Bible',cross_folder_summaries:'Cross-Folder Multi-Volume Memory',filter_scene_characters:'Scene Character Filtering',filter_extractor_entities:'Extractor Known Entity Filtering',enable_post_polish_reconciliation:'Post-Polish Term Reconciliation',enable_rag:'Hybrid RAG Enabled',enable_rag_reranker:'Enable Cross-Encoder Reranker',safety_recursive_subdivision:'Subdivision Enabled'};
  for(const label of Object.values(toggles)){const toggle=form.getByText(label,{exact:true}).locator('xpath=ancestor::*[.//button[@role="switch"]][1]').getByRole('switch'); if(await toggle.getAttribute('aria-checked')==='true')await toggle.click();}
  await form.getByLabel('Enable procedural learning').selectOption('true');await form.getByLabel('Learning cadence').selectOption('interval');
  await save(false);
  const cfg=await api(configEndpoint);
  const disk=diskYaml();
  expect(disk.enable_procedural_graph_learning).toBe(true);expect(disk.procedural_learning_cadence).toBe('interval');
  record('Native procedural enable/cadence persisted',['project.enable_procedural_graph_learning','project.procedural_learning_cadence'],[disk.enable_procedural_graph_learning,disk.procedural_learning_cadence],[true,'interval']);
  for(const [key,[expected]] of Object.entries(values)){expect(String(cfg.config[key])).toBe(expected);expect(String(disk[key])).toBe(expected);record('Native project control persisted',['project.'+key],String(disk[key]),expected);}
  for(const [key,value] of Object.entries(models)){expect(disk[key]).toBe(value);record('Native model route persisted',['project.'+key],disk[key],value);}
  for(const key of Object.keys(toggles)){expect(disk[key]).toBe(false);record('Native switch persisted',['project.'+key],disk[key],false);}
  for(const [i,[role]] of roles.entries()){const expected={temperature:Number((.3+i*.1).toFixed(1)),thinking_level:'low',thinking_budget:100+i,use_interactions_api:false};expect(disk.generation_settings[role]).toEqual(expected);record('Native role generation persisted',Object.keys(expected).map(k=>`project.generation_settings.${role}.${k}`),disk.generation_settings[role],expected);}
  await page.reload(); await expect(field(page.locator('form'),/^Novel Title$/)).toHaveValue(values.title[0]);
  for(const [value,label] of Object.values(values)) await expect(field(page.locator('form'),label)).toHaveValue(value);
  await page.screenshot({path:path.join(evidence,`native-${mode}-project.png`),fullPage:true});
  await open('global');
  const globals={};
  const simple=[['Language Defaults','SOURCE_LANG','Japanese'],['Language Defaults','TARGET_LANG','English'],['Quality Defaults','NOVEL_MAX_REVIEW_LOOPS','1'],['Quality Defaults','NOVEL_QUALITY_THRESHOLD','9.0'],['Memory & Entity Defaults','NOVEL_FILTER_EXTRACTOR_ENTITIES','false'],['Memory & Entity Defaults','NOVEL_POST_POLISH_RECONCILIATION','false'],['RAG Model Defaults','NOVEL_RAG_EMBEDDING_MODEL','mock-global-embedding'],['RAG Model Defaults','NOVEL_RAG_RERANKER_MODEL','mock-global-reranker'],['Rate Limit Defaults','NOVEL_MAX_TPM','45000'],['Rate Limit Defaults','NOVEL_MAX_RPM','70'],['Procedural Learning Defaults','NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING','true'],['Procedural Learning Defaults','NOVEL_PROCEDURAL_LEARNING_CADENCE','interval'],['Procedural Learning Defaults','NOVEL_PROCEDURAL_LEARNING_INTERVAL','20'],['Procedural Learning Defaults','NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES','3'],['Procedural Learning Defaults','NOVEL_PROCEDURAL_REFINER_MODEL','mock-refiner'],['Workspace Defaults','NOVEL_PROJECTS_DIR',path.dirname(project)],['Workspace Defaults','NOVEL_SCRAPER_PATH',path.join(path.dirname(project),'scraper')],['Workspace Defaults','NOVEL_SCRAPER_PYTHON',path.join(path.dirname(project),'python.exe')]];
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
  // Representative failures exercise the actual native settings form and real backend.
  await open('models');
  const invalidModel=page.getByLabel('Entity Extractor model model ID',{exact:true});
  const invalidCard=invalidModel.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]');
  await invalidCard.getByLabel('Temperature',{exact:true}).fill('3');
  let rejected=page.waitForResponse(r=>r.url().includes('/api/settings')&&r.request().method()==='PUT');
  await page.getByRole('button',{name:'Save Settings',exact:true}).click();expect((await rejected).status()).toBe(422);
  expect(diskYaml().generation_settings.extractor.temperature).toBe(.3);
  record('Native invalid temperature rejected without persistence',['project.generation_settings.extractor.temperature'],422,422);
  await open('general');
  await page.getByLabel('Novel Title',{exact:true}).fill('Unsaved native stale title');
  await api(configEndpoint,{genre:'native-concurrent-change'},'PUT');
  rejected=page.waitForResponse(r=>r.url().includes('/api/settings')&&r.request().method()==='PUT');
  await page.getByRole('button',{name:'Save Settings',exact:true}).click();expect((await rejected).status()).toBe(412);
  await expect(page.getByLabel('Novel Title',{exact:true})).toHaveValue('Unsaved native stale title');
  expect(diskYaml().title).toBe(values.title[0]);
  record('Native stale save rejected and draft preserved',['project.title','project.genre'],true,true);
  await open('chunking');
  await field(page.locator('form'),/^Chunk Overlap/).fill('0');await save(false);
  expect(diskYaml().chunk_overlap_lines).toBe(0);await page.reload();await expect(field(page.locator('form'),/^Chunk Overlap/)).toHaveValue('0');
  record('Native zero overlap persists and reloads',['project.chunk_overlap_lines'],0,0);
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
  await open('models');
  await page.getByRole('textbox',{name:'Search settings',exact:true}).fill('model');
  await expect(page.getByRole('button',{name:/Model Routing/})).toBeVisible();
  await page.getByRole('textbox',{name:'Search settings',exact:true}).fill('');
  record('Native settings category search',['action.category_search'],true,true);
  const beforePreset=await api(configEndpoint);const preset=beforePreset.available_presets[0];
  await page.locator('select').filter({has:page.locator('option',{hasText:'Apply Model Preset'})}).selectOption(preset.id);await save(false);
  for(const [key,value] of Object.entries(preset.models))expect(diskYaml()[key]).toBe(value);
  record('Native complete model preset',['action.apply_model_preset'],true,true);
  await page.getByTitle('Clear all project overrides to inherit 100% from .env',{exact:true}).click();await save(false);
  expect(diskYaml().model_name).toBeNull();expect(diskYaml().use_interactions_api).toBeNull();
  record('Native model and legacy reset',['action.clear_model_overrides'],true,true);
  await page.getByRole('button',{name:'Load .env',exact:true}).click();await save(false);
  expect(diskYaml().model_name).toBe(preset.models.model_name);
  record('Native load environment preset',['action.load_env_presets'],true,true);
  await api('/api/environment',{values:{CUSTOM_API_BASE_URL:'http://127.0.0.1:5194/v1'},api_keys:{CUSTOM_API_KEY:'synthetic-native-catalog-only'}},'PUT');
  await open('models');await page.getByRole('combobox',{name:'Primary model route provider',exact:true}).selectOption('custom');
  const catalogResponse=page.waitForResponse(r=>r.url().includes('/api/model-catalog')&&r.request().method()==='GET');
  await page.getByRole('button',{name:'Load custom catalog',exact:true}).first().click();expect((await catalogResponse).status()).toBe(200);
  await expect(page.getByRole('button',{name:/Refresh custom catalog/}).first()).toBeVisible();
  record('Native local provider catalog',['action.provider_catalog'],true,true);
  await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/settings?'+new URLSearchParams({project,section:'logs'}));
  const logsResponse=page.waitForResponse(r=>r.url().endsWith('/api/logs/info'));
  await page.getByRole('button',{name:'Refresh',exact:true}).click();expect((await logsResponse).status()).toBe(200);
  record('Native diagnostics refresh',['action.logs_refresh'],true,true);
  await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/settings?'+new URLSearchParams({project,section:'updates'}));
  await page.getByRole('button',{name:'Check for Updates',exact:true}).click();
  await expect(page.getByText(/Could not check GitHub releases/)).toBeVisible();
  record('Native controlled update error',['action.check_updates'],{local_feed:'204 no update',fallback:'502 refused loopback proxy',installed:false});
  await api('/api/environment',{values:{SOURCE_LANG:'Chinese',TARGET_LANG:'French'}},'PUT');
  for(const explicit of [false,true]) {
    await page.getByTitle('Initialize new novel project inside project/',{exact:true}).click();
    const createForm=page.locator('form').filter({has:page.locator('#new-project-title')});
    await expect(createForm.getByLabel('Source Language',{exact:true})).toHaveValue('Chinese');
    await expect(createForm.getByLabel('Target Language',{exact:true})).toHaveValue('French');
    const suffix=explicit?'override':'defaults';const folder=`created-native-${mode}-${suffix}-${Date.now()}`;const title=`Created native ${suffix}`;
    await createForm.getByLabel(/Novel Title/).fill(title);await createForm.getByLabel(/Project Name/).fill(folder);
    if(explicit){await createForm.getByLabel('Source Language',{exact:true}).fill('Korean');await createForm.getByLabel('Target Language',{exact:true}).fill('English');}
    await createForm.getByLabel('Novel Genre',{exact:true}).selectOption('romance');await createForm.getByLabel('Primary Model',{exact:true}).fill('mock-created');
    await page.screenshot({path:path.join(evidence,`native-${mode}-creation-${suffix}.png`),fullPage:true});
    const createdResponse=page.waitForResponse(r=>r.url().endsWith('/api/projects/create')&&r.request().method()==='POST');
    await createForm.getByRole('button',{name:'Initialize Project',exact:true}).click();const created=await createdResponse;expect(created.status()).toBe(200);
    const createdProject=(await created.json()).active_project.path;
    expect(path.relative(path.dirname(project),createdProject).startsWith('..')).toBe(false);expect(path.basename(createdProject)).toBe(folder);
    const expected={title,source_language:explicit?'Korean':'Chinese',target_language:explicit?'English':'French',genre:'romance',model_name:'mock-created'};
    const config=(await api('/api/settings?'+new URLSearchParams({project_path:createdProject}))).config;
    const createdDisk=fs.readFileSync(path.join(createdProject,'.novel/config.yaml'),'utf8');
    for(const [key,value] of Object.entries(expected)){expect(config[key]).toBe(value);expect(createdDisk).toContain(value);}
    await page.goto((mode==='dev'?'http://127.0.0.1:5187':base)+'/settings?'+new URLSearchParams({project:createdProject,section:'general'}));await page.reload();
    await expect(page.getByLabel('Novel Title',{exact:true})).toHaveValue(title);await expect(page.getByLabel('Source Language',{exact:true})).toHaveValue(expected.source_language);await expect(page.getByLabel('Target Language',{exact:true})).toHaveValue(expected.target_language);
    record('Native creation '+suffix+' UI/API/disk/reload',['creation.title','creation.folder_name','creation.source_language','creation.target_language','creation.genre','creation.model'],expected,expected);
  }
  if(mode==='release') {
    const hash=filename=>createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
    const finalEnvironment=await api('/api/environment');const configPath=path.join(project,'.novel/config.yaml');
    fs.writeFileSync(path.join(evidence,'native-release-lifecycle.json'),JSON.stringify({env_file_path:finalEnvironment.env_file_path,config_path:configPath,env_sha256_before_restart:hash(finalEnvironment.env_file_path),config_sha256_before_restart:hash(configPath)},null,2));
  }
  console.log(JSON.stringify({mode,setting_ids:new Set(observations.flatMap(r=>r.setting_ids)).size,observations:observations.length,completed:true}));
} catch(error) {
  observations.push({case:'Native browser audit interrupted',setting_ids:[],status:'blocked',reason:String(error)});saveEvidence();console.error(String(error));process.exitCode=1;
} finally {
  if(browser) await browser.close();
}
