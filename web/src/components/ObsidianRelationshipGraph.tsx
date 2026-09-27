import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import {
  forceSimulation,
  forceManyBody,
  forceCollide,
  forceLink,
  forceCenter,
  Simulation,
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

export interface GraphNode {
  id: string;
  name: string;
  originalName?: string;
  role?: string;
  relation?: string;
  categoryInfo: RelationshipCategoryInfo;
  isCenter: boolean;
  targetIndex: number;
  radius: number;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphLink {
  source: GraphNode | string;
  target: GraphNode | string;
  relation: string;
  color: string;
  category: string;
}

interface ObsidianRelationshipGraphProps {
  centerCharacter: BibleCharacter;
  relationships: Array<{
    targetName: string;
    relation: string;
    targetChar?: BibleCharacter;
    targetIndex: number;
    categoryInfo: RelationshipCategoryInfo;
  }>;
  onSelectCharacterByIndex: (index: number) => void;
  onSelectCharacterByName: (name: string) => void;
}

export const ObsidianRelationshipGraph: React.FC<ObsidianRelationshipGraphProps> = ({
  centerCharacter,
  relationships,
  onSelectCharacterByIndex,
  onSelectCharacterByName,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Filter & Search states
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [showLabels, setShowLabels] = useState<boolean>(true);

  // Physics parameter adjustments (Obsidian-style sliders)
  const [repulsionStrength, setRepulsionStrength] = useState<number>(-340);
  const [linkDistance, setLinkDistance] = useState<number>(120);
  const [collisionPadding, setCollisionPadding] = useState<number>(18);

  // Camera Pan and Zoom state
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  // Dragging interaction state
  const isDraggingNodeRef = useRef<boolean>(false);
  const isPanningCanvasRef = useRef<boolean>(false);
  const draggedNodeRef = useRef<GraphNode | null>(null);
  const dragStartPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const simulationRef = useRef<Simulation<GraphNode, any> | null>(null);
  const animationFrameIdRef = useRef<number | null>(null);

  // Synchronized Nodes and Links data
  const nodesRef = useRef<GraphNode[]>([]);
  const linksRef = useRef<GraphLink[]>([]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: relationships.length,
      ally: 0,
      rival: 0,
      family: 0,
      mentor: 0,
      acquaintance: 0,
    };
    relationships.forEach((r) => {
      const catId = r.categoryInfo.id;
      counts[catId] = (counts[catId] || 0) + 1;
    });
    return counts;
  }, [relationships]);

  // Construct Nodes & Links based on active filters
  useEffect(() => {
    const q = searchQuery.toLowerCase().trim();

    // 1. Center node
    const centerNode: GraphNode = {
      id: '__center__',
      name: centerCharacter.name,
      originalName: centerCharacter.original_name,
      role: centerCharacter.role || 'protagonist',
      isCenter: true,
      targetIndex: -1,
      radius: 25,
      x: 0,
      y: 0,
      fx: 0,
      fy: 0,
      categoryInfo: {
        color: '#d9a05b',
        badge: 'bg-[#383330] text-[#d9a05b] border-[#3f3a36]',
        category: 'Active Subject',
        id: 'ally',
      },
    };

    // 2. Peripheral nodes
    const filteredRels = relationships.filter((rel) => {
      // Category filter
      if (activeCategoryFilter !== 'all' && rel.categoryInfo.id !== activeCategoryFilter) {
        return false;
      }
      // Search query filter
      if (q) {
        const matchName = rel.targetName.toLowerCase().includes(q);
        const matchRel = rel.relation.toLowerCase().includes(q);
        const matchOrig = rel.targetChar?.original_name?.toLowerCase().includes(q);
        if (!matchName && !matchRel && !matchOrig) return false;
      }
      return true;
    });

    const newNodes: GraphNode[] = [centerNode];
    const newLinks: GraphLink[] = [];

    // Pre-calculate initial angles to seed the simulation gracefully
    const count = filteredRels.length;
    filteredRels.forEach((rel, idx) => {
      const angle = (2 * Math.PI * idx) / Math.max(1, count) - Math.PI / 2;
      const initialDist = 110 + (idx % 2) * 45;
      const x = Math.cos(angle) * initialDist;
      const y = Math.sin(angle) * initialDist;

      const node: GraphNode = {
        id: `rel_${idx}_${rel.targetName}`,
        name: rel.targetName,
        originalName: rel.targetChar?.original_name,
        role: rel.targetChar?.role || 'supporting',
        relation: rel.relation,
        categoryInfo: rel.categoryInfo,
        isCenter: false,
        targetIndex: rel.targetIndex,
        radius: 17,
        x,
        y,
      };

      newNodes.push(node);
      newLinks.push({
        source: centerNode.id,
        target: node.id,
        relation: rel.relation,
        color: rel.categoryInfo.color,
        category: rel.categoryInfo.category,
      });
    });

    nodesRef.current = newNodes;
    linksRef.current = newLinks;

    // Initialize or restart D3 physics simulation
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    const sim = forceSimulation<GraphNode>(newNodes)
      .force(
        'charge',
        forceManyBody<GraphNode>().strength((d) => (d.isCenter ? repulsionStrength * 1.5 : repulsionStrength))
      )
      .force(
        'collide',
        forceCollide<GraphNode>().radius((d) => d.radius + collisionPadding).iterations(3)
      )
      .force(
        'link',
        forceLink<GraphNode, any>(newLinks)
          .id((d) => d.id)
          .distance(linkDistance)
          .strength(0.65)
      )
      .force('center', forceCenter(0, 0).strength(0.04))
      .alphaDecay(0.025);

    simulationRef.current = sim;
    sim.alpha(1).restart();

    // Trigger re-render
    requestDraw();

    return () => {
      sim.stop();
    };
  }, [
    centerCharacter,
    relationships,
    activeCategoryFilter,
    searchQuery,
    repulsionStrength,
    linkDistance,
    collisionPadding,
  ]);

  // Request Animation Frame drawing function
  const requestDraw = useCallback(() => {
    if (animationFrameIdRef.current) return;
    animationFrameIdRef.current = requestAnimationFrame(() => {
      animationFrameIdRef.current = null;
      drawCanvas();
    });
  }, []);

  // Main Canvas Rendering Routine
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const dpr = window.devicePixelRatio || 1;

    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Background fill (Obsidian dark Warm Canvas aesthetic)
    ctx.fillStyle = '#201c19';
    ctx.fillRect(0, 0, width, height);

    // Subtle background coordinate grid dots
    ctx.fillStyle = '#2d2723';
    const gridSize = 40 * zoom;
    const offsetX = (width / 2 + pan.x) % gridSize;
    const offsetY = (height / 2 + pan.y) % gridSize;
    for (let x = offsetX; x < width; x += gridSize) {
      for (let y = offsetY; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.arc(x, y, 1, 0, 2 * Math.PI);
        ctx.fill();
      }
    }

    // Apply Camera Transform (Centered Pan & Zoom)
    ctx.translate(width / 2 + pan.x, height / 2 + pan.y);
    ctx.scale(zoom, zoom);

    const nodes = nodesRef.current;
    const links = linksRef.current;
    const hovered = hoveredNode;

    // 1. Draw Links (Obsidian spring connection lines)
    links.forEach((link) => {
      const source = typeof link.source === 'object' ? link.source : nodes.find((n) => n.id === link.source);
      const target = typeof link.target === 'object' ? link.target : nodes.find((n) => n.id === link.target);
      if (!source || !target) return;

      const isConnectedToHover =
        hovered && (hovered.id === source.id || hovered.id === target.id);

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);

      if (isConnectedToHover) {
        ctx.strokeStyle = link.color;
        ctx.lineWidth = 2.4;
        ctx.globalAlpha = 0.95;
        ctx.shadowColor = link.color;
        ctx.shadowBlur = 8;
        ctx.stroke();
      } else {
        ctx.strokeStyle = link.color;
        ctx.lineWidth = 1.2;
        ctx.globalAlpha = 0.35;
        ctx.setLineDash([3, 4]);
        ctx.stroke();
      }
      ctx.restore();

      // Render relationship text pill on the link if hovered or small roster
      const shouldDrawPill = isConnectedToHover || (nodes.length <= 10 && zoom >= 0.85);
      if (shouldDrawPill && link.relation) {
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2;
        const text = link.relation.length > 14 ? `${link.relation.slice(0, 13)}…` : link.relation;

        ctx.save();
        ctx.font = 'bold 9px "DM Mono", monospace';
        const textWidth = ctx.measureText(text).width;
        const pillW = textWidth + 12;
        const pillH = 16;

        ctx.fillStyle = '#24201d';
        ctx.strokeStyle = isConnectedToHover ? link.color : '#3f3a36';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(midX - pillW / 2, midY - pillH / 2, pillW, pillH, 3);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = isConnectedToHover ? link.color : '#dad2c1';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, midX, midY + 0.5);
        ctx.restore();
      }
    });

    // 2. Draw Nodes (Obsidian celestial spheres)
    nodes.forEach((node) => {
      const isHovered = hovered?.id === node.id;
      const isConnected =
        hovered &&
        links.some((l) => {
          const sId = typeof l.source === 'object' ? l.source.id : l.source;
          const tId = typeof l.target === 'object' ? l.target.id : l.target;
          return (sId === hovered.id && tId === node.id) || (tId === hovered.id && sId === node.id);
        });

      const isDimmed = hovered && !isHovered && !isConnected && !node.isCenter;
      const alpha = isDimmed ? 0.2 : 1.0;

      ctx.save();
      ctx.globalAlpha = alpha;

      // Outer Glow Halo on Center or Hovered node
      if (node.isCenter || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + (node.isCenter ? 8 : 6), 0, 2 * Math.PI);
        ctx.fillStyle = node.isCenter ? 'rgba(217, 160, 91, 0.18)' : `${node.categoryInfo.color}25`;
        ctx.fill();
      }

      // Main Node Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, 2 * Math.PI);
      ctx.fillStyle = node.isCenter ? '#383330' : '#2b2622';
      ctx.fill();

      // Border Ring
      ctx.lineWidth = node.isCenter ? 3 : isHovered ? 2.5 : 1.8;
      ctx.strokeStyle = node.isCenter
        ? '#d9a05b'
        : isHovered
        ? '#ffffff'
        : node.categoryInfo.color;
      if (isHovered || node.isCenter) {
        ctx.shadowColor = node.isCenter ? '#d9a05b' : node.categoryInfo.color;
        ctx.shadowBlur = node.isCenter ? 12 : 10;
      }
      ctx.stroke();

      // Node Initial Icon/Letter
      ctx.fillStyle = '#f7f5f0';
      ctx.font = `bold ${node.isCenter ? 12 : 10}px "DM Mono", monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const initial = (node.name || '?').charAt(0).toUpperCase();
      ctx.fillText(initial, node.x, node.y + (node.isCenter ? 0.5 : 0));

      // Node Label Text (Obsidian dynamic LOD)
      if (showLabels || isHovered || node.isCenter) {
        const labelText =
          node.name.length > 13 && !isHovered ? `${node.name.slice(0, 12)}…` : node.name;

        ctx.font = `${node.isCenter ? 'bold 11px' : isHovered ? 'bold 10px' : '500 10px'} "DM Mono", monospace`;
        const labelY = node.y + node.radius + (node.isCenter ? 14 : 11);

        // Label pill background for optimal legibility
        const textWidth = ctx.measureText(labelText).width;
        ctx.fillStyle = isHovered ? '#181513' : 'rgba(36, 32, 29, 0.85)';
        ctx.beginPath();
        ctx.roundRect(node.x - textWidth / 2 - 4, labelY - 7, textWidth + 8, 14, 2);
        ctx.fill();

        ctx.fillStyle = node.isCenter ? '#d9a05b' : isHovered ? '#f7f5f0' : '#dad2c1';
        ctx.fillText(labelText, node.x, labelY);
      }

      ctx.restore();
    });

    ctx.restore();
  }, [pan, zoom, hoveredNode, showLabels]);

  // Keep drawing while simulation is actively moving
  useEffect(() => {
    let animId: number;
    const loop = () => {
      drawCanvas();
      if (simulationRef.current && simulationRef.current.alpha() > 0.005) {
        animId = requestAnimationFrame(loop);
      }
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [drawCanvas]);

  // Coordinate Conversion Helper (Screen viewport -> Canvas World space)
  const screenToWorld = useCallback(
    (screenX: number, screenY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      const x = screenX - rect.left - canvas.clientWidth / 2 - pan.x;
      const y = screenY - rect.top - canvas.clientHeight / 2 - pan.y;
      return { x: x / zoom, y: y / zoom };
    },
    [pan, zoom]
  );

  // Find node under mouse coordinates
  const findNodeAt = useCallback(
    (worldX: number, worldY: number): GraphNode | null => {
      const nodes = nodesRef.current;
      for (let i = nodes.length - 1; i >= 0; i--) {
        const node = nodes[i];
        const dx = worldX - node.x;
        const dy = worldY - node.y;
        if (dx * dx + dy * dy <= (node.radius + 6) * (node.radius + 6)) {
          return node;
        }
      }
      return null;
    },
    []
  );

  // Mouse Interaction Handlers (Drag, Pan, Click, Hover)
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button !== 0) return; // Only primary button
    const world = screenToWorld(e.clientX, e.clientY);
    const clickedNode = findNodeAt(world.x, world.y);

    dragStartPosRef.current = { x: e.clientX, y: e.clientY };

    if (clickedNode) {
      isDraggingNodeRef.current = true;
      draggedNodeRef.current = clickedNode;

      if (!clickedNode.isCenter) {
        clickedNode.fx = clickedNode.x;
        clickedNode.fy = clickedNode.y;
      }

      if (simulationRef.current) {
        simulationRef.current.alphaTarget(0.3).restart();
      }
    } else {
      isPanningCanvasRef.current = true;
      panStartRef.current = { x: pan.x, y: pan.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const world = screenToWorld(e.clientX, e.clientY);

    // 1. Dragging Node (Obsidian dynamic spring physics)
    if (isDraggingNodeRef.current && draggedNodeRef.current) {
      const node = draggedNodeRef.current;
      if (!node.isCenter) {
        node.fx = world.x;
        node.fy = world.y;
      }
      requestDraw();
      return;
    }

    // 2. Panning Canvas
    if (isPanningCanvasRef.current) {
      const dx = e.clientX - dragStartPosRef.current.x;
      const dy = e.clientY - dragStartPosRef.current.y;
      setPan({
        x: panStartRef.current.x + dx,
        y: panStartRef.current.y + dy,
      });
      requestDraw();
      return;
    }

    // 3. Hovering check
    const node = findNodeAt(world.x, world.y);
    if (node !== hoveredNode) {
      setHoveredNode(node);
      requestDraw();
    }
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const dx = Math.abs(e.clientX - dragStartPosRef.current.x);
    const dy = Math.abs(e.clientY - dragStartPosRef.current.y);
    const isClick = dx < 5 && dy < 5;

    if (isDraggingNodeRef.current && draggedNodeRef.current) {
      const node = draggedNodeRef.current;

      if (isClick) {
        // Node was clicked! Navigate to dossier
        if (!node.isCenter) {
          if (node.targetIndex !== -1) {
            onSelectCharacterByIndex(node.targetIndex);
          } else {
            onSelectCharacterByName(node.name);
          }
        }
      }

      if (!node.isCenter) {
        // Release spring pin
        node.fx = null;
        node.fy = null;
      }

      isDraggingNodeRef.current = false;
      draggedNodeRef.current = null;

      if (simulationRef.current) {
        simulationRef.current.alphaTarget(0);
      }
    }

    isPanningCanvasRef.current = false;
  };

  const handleMouseLeave = () => {
    if (isDraggingNodeRef.current && draggedNodeRef.current) {
      if (!draggedNodeRef.current.isCenter) {
        draggedNodeRef.current.fx = null;
        draggedNodeRef.current.fy = null;
      }
      isDraggingNodeRef.current = false;
      draggedNodeRef.current = null;
      if (simulationRef.current) {
        simulationRef.current.alphaTarget(0);
      }
    }
    isPanningCanvasRef.current = false;
    setHoveredNode(null);
    requestDraw();
  };

  // Mouse Wheel Zoom centered on cursor
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.min(3.5, Math.max(0.35, zoom * zoomFactor));

    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - canvas.clientWidth / 2;
    const mouseY = e.clientY - rect.top - canvas.clientHeight / 2;

    // Anchor zoom around cursor position
    const newPanX = mouseX - (mouseX - pan.x) * (newZoom / zoom);
    const newPanY = mouseY - (mouseY - pan.y) * (newZoom / zoom);

    setZoom(newZoom);
    setPan({ x: newPanX, y: newPanY });
    requestDraw();
  };

  // Reset Camera View
  const handleResetCamera = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
    if (simulationRef.current) {
      simulationRef.current.alpha(0.3).restart();
    }
    requestDraw();
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[460px] bg-[#201c19] rounded-[4px] border border-[#3f3a36] overflow-hidden select-none flex flex-col"
    >
      {/* Top Floating Control Bar */}
      <div className="absolute top-2.5 left-2.5 right-2.5 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Left: Search & Category Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap pointer-events-auto">
          {/* Quick Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#857d75]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search graph..."
              className="pl-8 pr-6 py-1 bg-[#24201d]/90 backdrop-blur-sm border border-[#3f3a36] hover:border-[#b0a89f]/40 focus:border-[#d9a05b] rounded-[3px] text-xs font-mono text-[#f7f5f0] placeholder-[#857d75] focus:outline-none w-36 sm:w-44 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-2 text-[#857d75] hover:text-[#f7f5f0] cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Category Filter Pills */}
          <div className="flex items-center gap-1 bg-[#24201d]/90 backdrop-blur-sm p-0.5 rounded-[3px] border border-[#3f3a36] text-[11px] font-mono">
            <button
              onClick={() => setActiveCategoryFilter('all')}
              className={`px-2 py-0.5 rounded-[2px] transition-colors cursor-pointer ${
                activeCategoryFilter === 'all'
                  ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                  : 'text-[#857d75] hover:text-[#f7f5f0]'
              }`}
            >
              All ({categoryCounts.all})
            </button>
            {categoryCounts.ally > 0 && (
              <button
                onClick={() => setActiveCategoryFilter('ally')}
                className={`px-2 py-0.5 rounded-[2px] flex items-center gap-1 transition-colors cursor-pointer ${
                  activeCategoryFilter === 'ally'
                    ? 'bg-[#7fa678] text-[#1c241a] font-semibold'
                    : 'text-[#7fa678] hover:bg-[#7fa678]/10'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#7fa678]" />
                Allies ({categoryCounts.ally})
              </button>
            )}
            {categoryCounts.rival > 0 && (
              <button
                onClick={() => setActiveCategoryFilter('rival')}
                className={`px-2 py-0.5 rounded-[2px] flex items-center gap-1 transition-colors cursor-pointer ${
                  activeCategoryFilter === 'rival'
                    ? 'bg-[#cf6659] text-[#261614] font-semibold'
                    : 'text-[#cf6659] hover:bg-[#cf6659]/10'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#cf6659]" />
                Rivals ({categoryCounts.rival})
              </button>
            )}
            {categoryCounts.family > 0 && (
              <button
                onClick={() => setActiveCategoryFilter('family')}
                className={`px-2 py-0.5 rounded-[2px] flex items-center gap-1 transition-colors cursor-pointer ${
                  activeCategoryFilter === 'family'
                    ? 'bg-[#e699b8] text-[#2b1822] font-semibold'
                    : 'text-[#e699b8] hover:bg-[#e699b8]/10'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#e699b8]" />
                Family ({categoryCounts.family})
              </button>
            )}
            {categoryCounts.mentor > 0 && (
              <button
                onClick={() => setActiveCategoryFilter('mentor')}
                className={`px-2 py-0.5 rounded-[2px] flex items-center gap-1 transition-colors cursor-pointer ${
                  activeCategoryFilter === 'mentor'
                    ? 'bg-[#d9a05b] text-[#2b2114] font-semibold'
                    : 'text-[#d9a05b] hover:bg-[#d9a05b]/10'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#d9a05b]" />
                Mentors ({categoryCounts.mentor})
              </button>
            )}
          </div>
        </div>

        {/* Right: Physics Sliders Toggle & Zoom Status */}
        <div className="flex items-center gap-1 pointer-events-auto">
          <button
            onClick={() => setShowLabels(!showLabels)}
            className={`px-2 py-1 rounded-[3px] border border-[#3f3a36] text-[10px] font-mono cursor-pointer transition-colors ${
              showLabels
                ? 'bg-[#383330] text-[#f7f5f0]'
                : 'bg-[#24201d]/90 text-[#857d75] hover:text-[#f7f5f0]'
            }`}
            title="Toggle character labels"
          >
            Aa Labels
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1.5 rounded-[3px] border border-[#3f3a36] cursor-pointer transition-colors ${
              showSettings
                ? 'bg-[#d9a05b] text-[#2b2622]'
                : 'bg-[#24201d]/90 text-[#857d75] hover:text-[#f7f5f0]'
            }`}
            title="Physics Simulation Settings"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Physics Sliders Drawer (Obsidian Graph Forces) */}
      {showSettings && (
        <div className="absolute top-12 right-2.5 z-20 w-64 bg-[#24201d]/95 backdrop-blur-md border border-[#3f3a36] rounded-[4px] p-3 text-xs font-mono shadow-xl space-y-3">
          <div className="flex items-center justify-between pb-1.5 border-b border-[#3f3a36]">
            <span className="text-[11px] font-bold uppercase text-[#d9a05b] flex items-center gap-1">
              <SlidersHorizontal className="w-3 h-3" />
              Obsidian Physics Forces
            </span>
            <button
              onClick={() => setShowSettings(false)}
              className="text-[#857d75] hover:text-[#f7f5f0] cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-[#857d75]">
              <span>Node Repulsion</span>
              <span className="text-[#f7f5f0]">{Math.abs(repulsionStrength)}</span>
            </div>
            <input
              type="range"
              min="100"
              max="700"
              step="20"
              value={Math.abs(repulsionStrength)}
              onChange={(e) => setRepulsionStrength(-Number(e.target.value))}
              className="w-full accent-[#d9a05b] cursor-pointer"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-[#857d75]">
              <span>Link Distance (Spring)</span>
              <span className="text-[#f7f5f0]">{linkDistance}px</span>
            </div>
            <input
              type="range"
              min="60"
              max="240"
              step="10"
              value={linkDistance}
              onChange={(e) => setLinkDistance(Number(e.target.value))}
              className="w-full accent-[#d9a05b] cursor-pointer"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-[#857d75]">
              <span>Collision Padding</span>
              <span className="text-[#f7f5f0]">{collisionPadding}px</span>
            </div>
            <input
              type="range"
              min="8"
              max="35"
              step="2"
              value={collisionPadding}
              onChange={(e) => setCollisionPadding(Number(e.target.value))}
              className="w-full accent-[#d9a05b] cursor-pointer"
            />
          </div>
        </div>
      )}

      {/* Main Interactive HTML5 Canvas */}
      <canvas
        ref={canvasRef}
        className="w-full h-full cursor-grab active:cursor-grabbing block"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
      />

      {/* Hover Inspector Tooltip HUD (Obsidian Floating Card) */}
      {hoveredNode && !isDraggingNodeRef.current && (
        <div className="absolute bottom-3 left-3 z-10 bg-[#24201d]/95 backdrop-blur-md border border-[#3f3a36] rounded-[4px] p-3 max-w-xs shadow-xl pointer-events-none transition-all">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center font-mono font-bold text-xs border"
              style={{
                borderColor: hoveredNode.categoryInfo.color,
                backgroundColor: '#383330',
                color: '#f7f5f0',
              }}
            >
              {(hoveredNode.name || '?').charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-bold text-[#f7f5f0] truncate">{hoveredNode.name}</div>
              {hoveredNode.originalName && (
                <div className="text-[10px] font-mono text-[#857d75] truncate">
                  {hoveredNode.originalName}
                </div>
              )}
            </div>
          </div>

          <div className="mt-2 pt-2 border-t border-[#3f3a36]/60 flex items-center justify-between gap-2">
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded-[2px] font-mono border ${hoveredNode.categoryInfo.badge}`}
            >
              {hoveredNode.relation || hoveredNode.categoryInfo.category}
            </span>
            {!hoveredNode.isCenter && (
              <span className="text-[9px] font-mono text-[#857d75] flex items-center gap-1">
                Click to inspect dossier <ArrowRight className="w-2.5 h-2.5 text-[#d9a05b]" />
              </span>
            )}
          </div>
        </div>
      )}

      {/* Bottom-Right Camera Navigation Controls */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-1 bg-[#24201d]/90 backdrop-blur-sm p-1 rounded-[3px] border border-[#3f3a36]">
        <button
          onClick={() => {
            const newZoom = Math.min(3.5, zoom * 1.25);
            setZoom(newZoom);
            requestDraw();
          }}
          className="p-1 text-[#857d75] hover:text-[#f7f5f0] cursor-pointer transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => {
            const newZoom = Math.max(0.35, zoom * 0.8);
            setZoom(newZoom);
            requestDraw();
          }}
          className="p-1 text-[#857d75] hover:text-[#f7f5f0] cursor-pointer transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleResetCamera}
          className="p-1 text-[#857d75] hover:text-[#d9a05b] cursor-pointer transition-colors"
          title="Reset Camera & Center"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        <div className="px-1 text-[10px] font-mono text-[#857d75] border-l border-[#3f3a36]">
          {Math.round(zoom * 100)}%
        </div>
      </div>
    </div>
  );
};
