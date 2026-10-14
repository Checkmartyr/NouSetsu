import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import {
  forceSimulation,
  forceManyBody,
  forceCollide,
  forceLink,
  forceCenter,
  forceX,
  forceY,
  type Simulation,
} from 'd3-force';
import {
  Search,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  SlidersHorizontal,
  ArrowRight,
  X,
} from 'lucide-react';
import { BibleCharacter } from '../types/dashboard';

export interface RelationshipCategoryInfo {
  color: string;
  badge: string;
  category: string;
  id: 'family' | 'rival' | 'ally' | 'mentor' | 'acquaintance';
}

export function getEnhancedRelationshipCategory(rel: string): RelationshipCategoryInfo {
  const s = rel.toLowerCase();

  // 1. Family & Romance
  if (
    s.includes('sister') ||
    s.includes('brother') ||
    s.includes('mother') ||
    s.includes('father') ||
    s.includes('parent') ||
    s.includes('child') ||
    s.includes('son') ||
    s.includes('daughter') ||
    s.includes('family') ||
    s.includes('lover') ||
    s.includes('wife') ||
    s.includes('husband') ||
    s.includes('partner') ||
    s.includes('love') ||
    s.includes('fiancé') ||
    s.includes('fiancee') ||
    s.includes('spouse') ||
    // Thai keywords
    s.includes('ครอบครัว') ||
    s.includes('คนรัก') ||
    s.includes('พ่อ') ||
    s.includes('แม่') ||
    s.includes('พี่') ||
    s.includes('น้อง') ||
    s.includes('แฟน') ||
    s.includes('ลูก') ||
    s.includes('สามี') ||
    s.includes('ภรรยา') ||
    s.includes('คู่หมั้น') ||
    // CJK keywords
    s.includes('家族') ||
    s.includes('父') ||
    s.includes('母') ||
    s.includes('兄') ||
    s.includes('弟') ||
    s.includes('姉') ||
    s.includes('妹') ||
    s.includes('妻') ||
    s.includes('夫') ||
    s.includes('愛') ||
    s.includes('恋人') ||
    s.includes('婚約')
  ) {
    return {
      color: '#e699b8',
      badge: 'bg-[#383330] text-[#e699b8] border-[#3f3a36]',
      category: 'Family & Bond',
      id: 'family',
    };
  }

  // 2. Rival & Hostile
  if (
    s.includes('enemy') ||
    s.includes('rival') ||
    s.includes('nemesis') ||
    s.includes('hostile') ||
    s.includes('opponent') ||
    s.includes('foe') ||
    s.includes('threat') ||
    s.includes('adversary') ||
    s.includes('hate') ||
    // Thai keywords
    s.includes('ศัตรู') ||
    s.includes('คู่แข่ง') ||
    s.includes('ปรปักษ์') ||
    s.includes('แค้น') ||
    s.includes('คู่อาฆาต') ||
    // CJK keywords
    s.includes('敵') ||
    s.includes('ライバル') ||
    s.includes('仇') ||
    s.includes('仇敌') ||
    s.includes('宿敵')
  ) {
    return {
      color: '#cf6659',
      badge: 'bg-[#383330] text-[#cf6659] border-[#3f3a36]',
      category: 'Rival & Hostile',
      id: 'rival',
    };
  }

  // 3. Ally & Friend
  if (
    s.includes('ally') ||
    s.includes('friend') ||
    s.includes('comrade') ||
    s.includes('companion') ||
    s.includes('collaborator') ||
    s.includes('confidant') ||
    s.includes('sidekick') ||
    // Thai keywords
    s.includes('เพื่อน') ||
    s.includes('สหาย') ||
    s.includes('มิตร') ||
    s.includes('พันธมิตร') ||
    s.includes('พวกพ้อง') ||
    s.includes('คู่หู') ||
    // CJK keywords
    s.includes('友') ||
    s.includes('仲間') ||
    s.includes('同盟') ||
    s.includes('盟友') ||
    s.includes('親友')
  ) {
    return {
      color: '#7fa678',
      badge: 'bg-[#383330] text-[#7fa678] border-[#3f3a36]',
      category: 'Ally & Friend',
      id: 'ally',
    };
  }

  // 4. Mentor & Order
  if (
    s.includes('mentor') ||
    s.includes('master') ||
    s.includes('teacher') ||
    s.includes('disciple') ||
    s.includes('student') ||
    s.includes('servant') ||
    s.includes('lord') ||
    s.includes('leader') ||
    s.includes('boss') ||
    s.includes('subordinate') ||
    s.includes('guide') ||
    s.includes('guard') ||
    // Thai keywords
    s.includes('อาจารย์') ||
    s.includes('ครู') ||
    s.includes('ลูกศิษย์') ||
    s.includes('เจ้านาย') ||
    s.includes('หัวหน้า') ||
    s.includes('ผู้ติดตาม') ||
    s.includes('รับใช้') ||
    s.includes('ศิษย์') ||
    s.includes('ผู้นำ') ||
    // CJK keywords
    s.includes('師') ||
    s.includes('師匠') ||
    s.includes('弟子') ||
    s.includes('主') ||
    s.includes('主従') ||
    s.includes('宗主') ||
    s.includes('先生') ||
    s.includes('指導')
  ) {
    return {
      color: '#d9a05b',
      badge: 'bg-[#383330] text-[#d9a05b] border-[#3f3a36]',
      category: 'Mentor & Order',
      id: 'mentor',
    };
  }

  // 5. Default Acquaintance
  return {
    color: '#8b9bb4',
    badge: 'bg-[#383330] text-[#8b9bb4] border-[#3f3a36]',
    category: 'Acquaintance',
    id: 'acquaintance',
  };
}

interface GraphNode {
  id: string;
  name: string;
  originalName?: string;
  aliases: string[];
  role?: string;
  targetIndex: number;
  radius: number;
  x: number;
  y: number;
  fx?: number | null;
  fy?: number | null;
}
interface RelationshipRecord {
  from: string;
  to: string;
  relation: string;
  categoryInfo: RelationshipCategoryInfo;
}
interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  records: RelationshipRecord[];
}
interface PersonalRelationship {
  targetName: string;
  relation: string;
  targetChar?: BibleCharacter;
  targetIndex: number;
  categoryInfo: RelationshipCategoryInfo;
}
interface ObsidianRelationshipGraphProps {
  centerCharacter: BibleCharacter;
  relationships: PersonalRelationship[];
  onSelectCharacterByIndex: (index: number) => void;
  onSelectCharacterByName: (name: string) => void;
  characters?: BibleCharacter[];
  selectedCharacterIndex?: number;
  selectionRevision?: number;
  onOpenDossier?: (index: number) => void;
}

const normalize = (name: string) => name.trim().toLocaleLowerCase();
const endpointId = (endpoint: string | GraphNode) => typeof endpoint === 'string' ? endpoint : endpoint.id;
const roleColors: Record<string, string> = {
  protagonist: '#d9a05b', antagonist: '#cf6659', supporting: '#8b9bb4', mentor: '#b0a89f', minor: '#857d75',
};
const categories = ['family', 'rival', 'ally', 'mentor', 'acquaintance'] as const;
const categoryNames = { family: 'Family & Bond', rival: 'Rival & Hostile', ally: 'Ally & Friend', mentor: 'Mentor & Order', acquaintance: 'Acquaintance' };
const categoryColors = { family: '#e699b8', rival: '#cf6659', ally: '#7fa678', mentor: '#d9a05b', acquaintance: '#8b9bb4' };

// Resolve exact identities before aliases; ambiguous aliases stay unresolved.
export function resolveCharacterIndex(characters: BibleCharacter[], name: string): number {
  const key = normalize(name);
  const exact = characters.map((c, i) => ({ c, i })).filter(({ c }) => normalize(c.name) === key || normalize(c.original_name) === key);
  if (exact.length === 1) return exact[0].i;
  if (exact.length > 1) return -1;
  const aliases = characters.map((c, i) => ({ c, i })).filter(({ c }) => c.aliases?.some(a => normalize(a) === key));
  return aliases.length === 1 ? aliases[0].i : -1;
}

export function buildRelationshipNetwork(characters: BibleCharacter[]) {
  const identities = new Map<string, number>();
  const nodes: GraphNode[] = characters.map((c, index) => {
    const identity = JSON.stringify([normalize(c.original_name), normalize(c.name)]);
    const occurrence = identities.get(identity) || 0;
    identities.set(identity, occurrence + 1);
    return {
      id: `character:${identity}:${occurrence}`, name: c.name, originalName: c.original_name,
      aliases: c.aliases || [], role: c.role, targetIndex: index, radius: 19, x: 0, y: 0,
    };
  });
  const pairs = new Map<string, GraphLink>();
  characters.forEach((c, index) => {
    Object.entries(c.relationships || {}).forEach(([name, relation]) => {
      const targetIndex = resolveCharacterIndex(characters, name);
      const targetId = targetIndex >= 0 ? nodes[targetIndex].id : `unresolved:${normalize(name)}`;
      if (!nodes.some(n => n.id === targetId)) nodes.push({ id: targetId, name, aliases: [], targetIndex: -1, radius: 17, x: 0, y: 0 });
      const sourceId = nodes[index].id;
      const key = JSON.stringify([sourceId, targetId].sort());
      const link = pairs.get(key) || { source: sourceId, target: targetId, records: [] };
      link.records.push({ from: sourceId, to: targetId, relation, categoryInfo: getEnhancedRelationshipCategory(relation) });
      pairs.set(key, link);
    });
  });
  return { nodes, links: [...pairs.values()] };
}

export const ObsidianRelationshipGraph: React.FC<ObsidianRelationshipGraphProps> = ({
  centerCharacter, relationships, onSelectCharacterByIndex, onSelectCharacterByName,
  characters, selectedCharacterIndex, selectionRevision = 0, onOpenDossier,
}) => {
  const global = characters !== undefined;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<Simulation<GraphNode, GraphLink> | null>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const linksRef = useRef<GraphLink[]>([]);
  const frameRef = useRef<number | null>(null);
  const drawRef = useRef<() => void>(() => {});
  const camera = useRef({ zoom: 1, x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [repulsion, setRepulsion] = useState(340);
  const [distance, setDistance] = useState(170);
  const [padding, setPadding] = useState(18);
  const gesture = useRef<{ node?: GraphNode; x: number; y: number; panX: number; panY: number; moved: boolean } | null>(null);
  const buttonClass = 'px-2 py-1.5 rounded border border-[#3f3a36] bg-[#24201d] text-[#dad2c1] hover:bg-[#383330] focus-visible:outline focus-visible:outline-[#d9a05b] cursor-pointer';

  const globalData = useMemo(() => characters ? buildRelationshipNetwork(characters) : null, [characters]);
  const lastSelection = useRef({ index: selectedCharacterIndex, revision: selectionRevision });
  const data = useMemo(() => {
    if (globalData) return globalData;
    const center: GraphNode = { id: 'center', name: centerCharacter.name, originalName: centerCharacter.original_name,
      aliases: centerCharacter.aliases || [], role: centerCharacter.role, targetIndex: -1, radius: 25, x: 0, y: 0, fx: 0, fy: 0 };
    const nodes: GraphNode[] = [center];
    const links: GraphLink[] = [];
    relationships.forEach(r => {
      const id = r.targetIndex >= 0 ? `character:${r.targetIndex}` : `unresolved:${normalize(r.targetName)}`;
      if (!nodes.some(n => n.id === id)) nodes.push({ id, name: r.targetChar?.name || r.targetName,
        originalName: r.targetChar?.original_name, aliases: r.targetChar?.aliases || [], role: r.targetChar?.role,
        targetIndex: r.targetIndex, radius: 19, x: 0, y: 0 });
      const record = { from: center.id, to: id, relation: r.relation, categoryInfo: r.categoryInfo };
      const existing = links.find(l => l.target === id);
      if (existing) existing.records.push(record);
      else links.push({ source: center.id, target: id, records: [record] });
    });
    return { nodes, links };
  }, [globalData, centerCharacter, relationships]);

  const filtered = useMemo(() => {
    const q = normalize(query);
    const matched = new Set(data.nodes.filter(n => [n.name, n.originalName || '', ...n.aliases].some(s => normalize(s).includes(q))).map(n => n.id));
    const links = data.links.map(l => ({ ...l, records: l.records.filter(r => category === 'all' || r.categoryInfo.id === category) }))
      .filter(l => l.records.length && (!q || matched.has(endpointId(l.source)) || matched.has(endpointId(l.target)) || l.records.some(r => normalize(r.relation).includes(q))));
    const endpoints = new Set(links.flatMap(l => [endpointId(l.source), endpointId(l.target)]));
    const nodes = data.nodes.filter(n => (!q && category === 'all') || endpoints.has(n.id) || (category === 'all' && matched.has(n.id)) || (!global && n.id === 'center'));
    return { nodes, links };
  }, [data, query, category, global]);

  const requestDraw = useCallback(() => {
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(() => { frameRef.current = null; drawRef.current(); });
  }, []);
  const setCamera = useCallback((next: { zoom: number; x: number; y: number }) => {
    camera.current = next; setZoom(next.zoom); requestDraw();
  }, [requestDraw]);
  const fit = useCallback(() => {
    const canvas = canvasRef.current;
    const nodes = nodesRef.current;
    if (!canvas || !nodes.length) return;
    const extent = (n: GraphNode) => Math.max(n.radius + 12, n.name.length * 3.8 + 8);
    const minX = Math.min(...nodes.map(n => n.x - extent(n)));
    const maxX = Math.max(...nodes.map(n => n.x + extent(n)));
    const minY = Math.min(...nodes.map(n => n.y - n.radius - 12));
    const maxY = Math.max(...nodes.map(n => n.y + n.radius + 32));
    const z = Math.min(1.6, Math.max(0.08, Math.min((canvas.clientWidth - 48) / (maxX - minX), (canvas.clientHeight - 48) / (maxY - minY))));
    setCamera({ zoom: z, x: -(minX + maxX) * z / 2, y: -(minY + maxY) * z / 2 });
  }, [setCamera]);

  useEffect(() => {
    const previous = new Map(nodesRef.current.map(n => [n.id, n]));
    const nodes = filtered.nodes.map((n, i) => {
      const old = previous.get(n.id);
      const angle = i * Math.PI * (3 - Math.sqrt(5));
      const radius = 65 * Math.sqrt(i + 1);
      return { ...n, x: old?.x ?? Math.cos(angle) * radius, y: old?.y ?? Math.sin(angle) * radius };
    });
    const links = filtered.links.map(l => ({ ...l }));
    nodesRef.current = nodes; linksRef.current = links;
    const sim = forceSimulation<GraphNode>(nodes)
      .force('charge', forceManyBody<GraphNode>().strength(-repulsion))
      .force('collide', forceCollide<GraphNode>().radius(n => Math.max(n.radius + padding, n.name.length * 3.8 + padding)).iterations(3))
      .force('link', forceLink<GraphNode, GraphLink>(links).id(n => n.id).distance(distance).strength(0.35))
      .force('center', forceCenter(0, 0)).stop();
    const aspect = Math.max(1, (canvasRef.current?.clientWidth || 600) / (canvasRef.current?.clientHeight || 400));
    // Keep isolates near the cast and favor a wide layout on desktop.
    sim.force('x', forceX<GraphNode>(0).strength(0.025 / aspect));
    sim.force('y', forceY<GraphNode>(0).strength(0.07 * aspect));
    // Settle once before fitting so filtering never opens on an overlapping layout.
    sim.tick(180);
    simulationRef.current = sim;
    sim.on('tick', requestDraw);
    fit(); requestDraw();
    return () => { sim.stop(); if (simulationRef.current === sim) simulationRef.current = null; };
  }, [filtered, repulsion, distance, padding, fit, requestDraw]);

  useEffect(() => {
    if (!global || (lastSelection.current.index === selectedCharacterIndex && lastSelection.current.revision === selectionRevision)) return;
    lastSelection.current = { index: selectedCharacterIndex, revision: selectionRevision };
    setSelected(data.nodes.find(n => n.targetIndex === selectedCharacterIndex)?.id || null);
  }, [selectedCharacterIndex, selectionRevision, data, global]);
  useEffect(() => { setHovered(null); }, [filtered]);
  useEffect(() => {
    const observer = new ResizeObserver(() => { fit(); requestDraw(); });
    if (viewportRef.current) observer.observe(viewportRef.current);
    return () => { observer.disconnect(); if (frameRef.current !== null) cancelAnimationFrame(frameRef.current); frameRef.current = null; };
  }, [fit, requestDraw]);

  const focused = filtered.nodes.find(n => n.id === (hovered || selected));
  const focusedId = focused?.id || null;
  const incident = filtered.links.filter(l => endpointId(l.source) === focusedId || endpointId(l.target) === focusedId);
  const neighbors = new Set(incident.flatMap(l => [endpointId(l.source), endpointId(l.target)]));
  drawRef.current = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const w = canvas.clientWidth, h = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#201c19'; ctx.fillRect(0, 0, w, h);
    const cam = camera.current;
    ctx.translate(w / 2 + cam.x, h / 2 + cam.y); ctx.scale(cam.zoom, cam.zoom);
    const byId = new Map(nodesRef.current.map(n => [n.id, n]));
    linksRef.current.forEach(l => {
      const a = byId.get(endpointId(l.source)), b = byId.get(endpointId(l.target));
      if (!a || !b) return;
      const active = a.id === focusedId || b.id === focusedId;
      ctx.globalAlpha = focusedId ? active ? 0.9 : 0.12 : 0.45;
      ctx.strokeStyle = l.records[0].categoryInfo.color; ctx.lineWidth = (active ? 2 : 1) / cam.zoom;
      ctx.beginPath(); ctx.moveTo(a.x, a.y);
      if (a.id === b.id) ctx.arc(a.x + 22, a.y - 22, 26, 0, 2 * Math.PI);
      else ctx.lineTo(b.x, b.y);
      ctx.stroke();
      if (active) {
        const text = l.records.map(r => r.relation).join(' / ');
        const label = text.length > 30 ? text.slice(0, 29) + '…' : text;
        const x = (a.x + b.x) / 2, y = (a.y + b.y) / 2;
        ctx.font = `${12 / cam.zoom}px sans-serif`;
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = '#24201d'; ctx.fillRect(x - tw / 2 - 5 / cam.zoom, y - 9 / cam.zoom, tw + 10 / cam.zoom, 18 / cam.zoom);
        ctx.fillStyle = '#f7f5f0'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, x, y);
      }
    });
    nodesRef.current.forEach(n => {
      const active = n.id === focusedId;
      ctx.globalAlpha = focusedId && !active && !neighbors.has(n.id) ? 0.25 : 1;
      const color = roleColors[(n.role || 'minor').toLowerCase()] || roleColors.minor;
      ctx.fillStyle = active ? '#383330' : '#2b2622'; ctx.strokeStyle = active ? '#f7f5f0' : color; ctx.lineWidth = (active ? 3 : 1.5) / cam.zoom;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#f7f5f0'; ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(Array.from(n.name)[0] || '?', n.x, n.y);
    });
    // ponytail: bounded label placement for novel casts; use spatial indexing if large rosters make redraws slow.
    // Place screen-sized name labels independently of physics to avoid overlaps at fit zoom.
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const anchors = nodesRef.current.map(n => ({ n, x: w / 2 + cam.x + n.x * cam.zoom, y: h / 2 + cam.y + n.y * cam.zoom, r: n.radius * cam.zoom }));
    const occupied: { x: number; y: number; w: number; h: number }[] = [];
    const labels: { n: GraphNode; x: number; y: number; r: number; active: boolean; text: string; font: string; box: { x: number; y: number; w: number; h: number } }[] = [];
    let needsLabelGrid = false;
    anchors.sort((a, b) => Number(b.n.id === focusedId) - Number(a.n.id === focusedId));
    anchors.forEach(({ n, x, y, r }) => {
      const active = n.id === focusedId;
      if (x + r < 0 || x - r > w || y + r < 0 || y - r > h) return;
      if (!showLabels && !active && n.id !== 'center') return;
      ctx.font = `${active ? 'bold ' : ''}${w < 500 ? 11 : 12}px sans-serif`;
      const label = n.name.length > 26 ? n.name.slice(0, 25) + '…' : n.name;
      const width = ctx.measureText(label).width + 8;
      const offsets = [[0, r + 16], [0, -r - 16], [r + width / 2 + 8, 0], [-r - width / 2 - 8, 0]];
      for (let ring = 1; ring <= 16; ring++) {
        for (let step = 0; step < 12; step++) {
          const angle = step * Math.PI / 6;
          offsets.push([Math.cos(angle) * ring * 20, Math.sin(angle) * ring * 20]);
        }
      }
      let box = { x: x - width / 2, y: y + r + 7, w: width, h: 18 };
      let placed = false;
      const isFree = (candidate: typeof box) => {
        const intersectsLabel = occupied.some(b => candidate.x < b.x + b.w + 4 && candidate.x + candidate.w + 4 > b.x && candidate.y < b.y + b.h + 3 && candidate.y + candidate.h + 3 > b.y);
        const intersectsNode = anchors.some(a => candidate.x < a.x + a.r + 3 && candidate.x + candidate.w > a.x - a.r - 3 && candidate.y < a.y + a.r + 3 && candidate.y + candidate.h > a.y - a.r - 3);
        return !intersectsLabel && !intersectsNode;
      };
      for (const [dx, dy] of offsets) {
        const candidate = { x: Math.min(w - width - 4, Math.max(4, x + dx - width / 2)), y: Math.min(h - 22, Math.max(4, y + dy - 9)), w: width, h: 18 };
        if (isFree(candidate)) { box = candidate; placed = true; break; }
      }
      needsLabelGrid ||= !placed;
      occupied.push(box);
      labels.push({ n, x, y, r, active, text: label, font: ctx.font, box });
    });
    // If local placement runs out of room, use aligned labels with leader lines.
    // This preserves every name on narrow canvases instead of stacking labels.
    if (needsLabelGrid && labels.length) {
      const columnWidth = Math.max(...labels.map(l => l.box.w)) + 8;
      const columns = Math.max(1, Math.floor((w - 8) / columnWidth));
      const rows = Math.ceil(labels.length / columns);
      labels.sort((a, b) => a.y - b.y);
      for (let row = 0; row < rows; row++) {
        const group = labels.slice(row * columns, (row + 1) * columns).sort((a, b) => a.x - b.x);
        group.forEach((label, column) => {
          label.box.x = (column + 0.5) * w / columns - label.box.w / 2;
          label.box.y = (row + 0.5) * h / rows - 9;
        });
      }
    }
    labels.forEach(({ n, x, y, r, active, text: label, font, box }) => {
      ctx.font = font;
      ctx.globalAlpha = focusedId && !active && !neighbors.has(n.id) ? 0.25 : 1;
      const labelX = box.x + box.w / 2, labelY = box.y + box.h / 2;
      if (Math.hypot(labelX - x, labelY - y) > r + 22) {
        ctx.strokeStyle = '#857d75'; ctx.lineWidth = 0.6;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(labelX, labelY); ctx.stroke();
      }
      ctx.fillStyle = '#201c19'; ctx.fillRect(box.x, box.y, box.w, box.h);
      ctx.fillStyle = active ? '#ffffff' : '#dad2c1'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, labelX, labelY);
    });
    ctx.globalAlpha = 1;
  };
  useEffect(() => { requestDraw(); }, [focusedId, filtered, showLabels, requestDraw]);

  const hit = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect(), cam = camera.current;
    const x = (clientX - rect.left - canvas.clientWidth / 2 - cam.x) / cam.zoom;
    const y = (clientY - rect.top - canvas.clientHeight / 2 - cam.y) / cam.zoom;
    return { x, y, node: [...nodesRef.current].reverse().find(n => Math.hypot(n.x - x, n.y - y) <= n.radius + 6 / cam.zoom) };
  };
  const choose = (node: GraphNode) => {
    if (global) { setSelected(node.id); if (node.targetIndex >= 0) onSelectCharacterByIndex(node.targetIndex); }
    else if (node.id !== 'center') { if (node.targetIndex >= 0) onSelectCharacterByIndex(node.targetIndex); else onSelectCharacterByName(node.name); }
  };
  const endGesture = (e: React.PointerEvent<HTMLCanvasElement>, cancelled = false) => {
    const g = gesture.current;
    if (!g) return;
    if (g.node) {
      if (!g.moved && !cancelled) choose(g.node);
      if (g.node.id !== 'center') { g.node.fx = null; g.node.fy = null; }
    }
    gesture.current = null;
    simulationRef.current?.alphaTarget(0);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
    requestDraw();
  };
  const zoomAt = (factor: number, x = 0, y = 0) => {
    const cam = camera.current, z = Math.min(4, Math.max(0.08, cam.zoom * factor));
    setCamera({ zoom: z, x: x - (x - cam.x) * z / cam.zoom, y: y - (y - cam.y) * z / cam.zoom });
  };
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left - canvas.clientWidth / 2, e.clientY - rect.top - canvas.clientHeight / 2);
    };
    canvas.addEventListener('wheel', wheel, { passive: false });
    return () => canvas.removeEventListener('wheel', wheel);
  }, [setCamera]);

  return <section aria-label={global ? 'Global relationship graph' : 'Personal relationship graph'} className="w-full min-w-0 rounded border border-[#3f3a36] bg-[#201c19] text-xs text-[#dad2c1]">
    <div className="flex flex-wrap items-center gap-2 p-3 border-b border-[#3f3a36]">
      <label className="flex items-center gap-2"><Search size={14} /><input aria-label="Search graph" placeholder="Search graph..." value={query} onChange={e => setQuery(e.target.value)} className="w-40 bg-[#24201d] border border-[#3f3a36] rounded p-1.5" /></label>
      <button className={buttonClass} aria-pressed={category === 'all'} onClick={() => setCategory('all')}>All</button>
      {categories.map(id => <button key={id} className={buttonClass} style={{ color: categoryColors[id], borderColor: category === id ? categoryColors[id] : undefined }} aria-pressed={category === id} onClick={() => setCategory(id)}>{categoryNames[id]}</button>)}
      <button className={buttonClass} title="Toggle character labels" aria-pressed={showLabels} onClick={() => setShowLabels(v => !v)}>Aa Labels</button>
      <button className={buttonClass} title="Physics Simulation Settings" aria-expanded={showSettings} onClick={() => setShowSettings(v => !v)}><SlidersHorizontal size={14} /><span className="sr-only">Layout settings</span></button>
    </div>
    {showSettings && <div className="flex flex-wrap gap-4 p-3 border-b border-[#3f3a36]">
      <strong>Obsidian Physics Forces</strong>
      {([['Node Repulsion', repulsion, 100, 700, setRepulsion], ['Link Distance', distance, 60, 300, setDistance], ['Collision Padding', padding, 8, 40, setPadding]] as const).map(([label, value, min, max, setter]) => <label key={label}>{label} ({value})<input aria-label={label} type="range" min={min} max={max} value={value} onChange={e => setter(Number(e.target.value))} className="block accent-[#d9a05b]" /></label>)}
    </div>}
    <div className="flex flex-wrap items-center gap-3 p-2 text-[11px] text-[#b0a89f]">
      <span role="status">{filtered.nodes.length} characters · {filtered.links.length} connections</span>
      {Object.entries(roleColors).map(([role, color]) => <span key={role} className="flex items-center gap-1 capitalize"><span style={{ background: color }} className="w-2 h-2 rounded-full" />{role}</span>)}
      <span>Node: role · Line: relationship</span>
    </div>
    <div ref={viewportRef} className={global ? 'relative h-[52vh] min-h-[350px] max-h-[700px]' : 'relative h-[400px]'}>
      <canvas ref={canvasRef} aria-label="Interactive character relationship canvas; use the roster or character buttons below for keyboard selection" className="block w-full h-full touch-none cursor-grab active:cursor-grabbing"
        onPointerDown={e => {
          if (e.button !== 0) return;
          const { node } = hit(e.clientX, e.clientY);
          gesture.current = { node, x: e.clientX, y: e.clientY, panX: camera.current.x, panY: camera.current.y, moved: false };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={e => {
          const world = hit(e.clientX, e.clientY), g = gesture.current;
          if (!g) { setHovered(world.node?.id || null); return; }
          const dx = e.clientX - g.x, dy = e.clientY - g.y;
          g.moved ||= Math.hypot(dx, dy) > 5;
          if (!g.moved) return;
          if (g.node && g.node.id !== 'center') { g.node.fx = world.x; g.node.fy = world.y; simulationRef.current?.alphaTarget(0.15).restart(); }
          else if (!g.node) setCamera({ ...camera.current, x: g.panX + dx, y: g.panY + dy });
          requestDraw();
        }} onPointerUp={e => endGesture(e)} onPointerCancel={e => endGesture(e, true)} onLostPointerCapture={e => endGesture(e, true)} onPointerLeave={() => { if (!gesture.current) setHovered(null); }} />
      {filtered.nodes.length === 0 && <p className="absolute inset-0 flex items-center justify-center pointer-events-none">No matching characters or relationships.</p>}
    </div>
    <div className="flex flex-wrap gap-2 items-center p-2 border-t border-[#3f3a36]">
      <button className={buttonClass} title="Zoom In" onClick={() => zoomAt(1.25)}><ZoomIn size={14} /><span className="sr-only">Zoom in</span></button>
      <button className={buttonClass} title="Zoom Out" onClick={() => zoomAt(0.8)}><ZoomOut size={14} /><span className="sr-only">Zoom out</span></button>
      <button className={buttonClass} title="Reset Camera & Center" onClick={fit}><RotateCcw size={14} className="inline mr-1" />Fit graph</button>
      {global && <button className={buttonClass} onClick={() => { setSelected(null); setHovered(null); }}><X size={12} className="inline mr-1" />Clear selection</button>}
      <span aria-label="Graph zoom">{Math.round(zoom * 100)}%</span><span className="text-[#857d75]">Drag nodes to arrange · Drag background to pan · Scroll to zoom</span>
    </div>
    <div aria-label="Relationship details" className="p-3 border-t border-[#3f3a36] max-h-64 overflow-y-auto">
      {focused ? <>
        <div className="flex flex-wrap gap-2 items-center"><strong className="text-[#f7f5f0]">{focused.name}</strong><span>{focused.originalName}</span>
          {global && focused.targetIndex >= 0 && onOpenDossier && <button className={buttonClass} onClick={() => onOpenDossier(focused.targetIndex)}>Open dossier <ArrowRight size={12} className="inline" /></button>}
          {focused.targetIndex < 0 && global && <span>Unregistered character</span>}
        </div>
        {incident.length ? <ul className="mt-2 space-y-2">{incident.flatMap(l => l.records).map((r, i) => <li key={i} style={{ borderColor: r.categoryInfo.color }} className="border-l-2 pl-2 break-words">
          <span>{data.nodes.find(n => n.id === r.from)?.name} → {data.nodes.find(n => n.id === r.to)?.name}: </span><span>{r.relation}</span>
        </li>)}</ul> : <p className="mt-2">No connections in this view.</p>}
      </> : <p>Select or hover a character to explore their connections.</p>}
    </div>
    <details className="border-t border-[#3f3a36] p-2"><summary className="cursor-pointer">Choose a character ({filtered.nodes.length})</summary><div className="flex flex-wrap gap-2 mt-2">{filtered.nodes.map(n => <button key={n.id} className={buttonClass} aria-pressed={selected === n.id} onClick={() => choose(n)}>{n.name}</button>)}</div></details>
  </section>;
};
