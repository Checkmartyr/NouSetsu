import React, { useState, useMemo } from 'react';
import {
  Crown,
  Swords,
  Shield,
  Award,
  User,
  MessageSquare,
  Search,
  Sparkles,
  Network,
  Share2,
  Edit2,
  ArrowRight,
  Zap,
  Info,
  Plus,
  Compass,
  Users
} from 'lucide-react';
import { BibleCharacter } from '../types/dashboard';

interface CharacterVisualizerProps {
  characters: BibleCharacter[];
  selectedCharacterIndex?: number | null;
  onSelectCharacter?: (index: number) => void;
  onEditCharacter?: (char: BibleCharacter, index: number) => void;
  onAddCharacter?: () => void;
}

// Role thematic configurations
const ROLE_CONFIGS: Record<
  string,
  {
    label: string;
    badgeClass: string;
    gradient: string;
    border: string;
    glow: string;
    color: string;
    icon: React.FC<{ className?: string }>;
  }
> = {
  protagonist: {
    label: 'Protagonist',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    gradient: 'from-amber-500/20 via-orange-500/10 to-transparent',
    border: 'border-amber-500/50',
    glow: 'shadow-amber-500/20 ring-amber-400/30',
    color: '#f59e0b',
    icon: Crown,
  },
  antagonist: {
    label: 'Antagonist',
    badgeClass: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    gradient: 'from-rose-500/20 via-red-500/10 to-transparent',
    border: 'border-rose-500/50',
    glow: 'shadow-rose-500/20 ring-rose-400/30',
    color: '#f43f5e',
    icon: Swords,
  },
  supporting: {
    label: 'Supporting',
    badgeClass: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    gradient: 'from-indigo-500/20 via-blue-500/10 to-transparent',
    border: 'border-indigo-500/50',
    glow: 'shadow-indigo-500/20 ring-indigo-400/30',
    color: '#6366f1',
    icon: Shield,
  },
  mentor: {
    label: 'Mentor',
    badgeClass: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    gradient: 'from-purple-500/20 via-fuchsia-500/10 to-transparent',
    border: 'border-purple-500/50',
    glow: 'shadow-purple-500/20 ring-purple-400/30',
    color: '#a855f7',
    icon: Award,
  },
  minor: {
    label: 'Minor',
    badgeClass: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    gradient: 'from-slate-700/20 via-slate-800/10 to-transparent',
    border: 'border-slate-600/50',
    glow: 'shadow-slate-500/20 ring-slate-400/30',
    color: '#64748b',
    icon: User,
  },
};

function getRoleConfig(role?: string) {
  const r = (role || 'minor').toLowerCase();
  return ROLE_CONFIGS[r] || ROLE_CONFIGS.minor;
}

// Relationship category detection
function getRelationshipCategory(rel: string): {
  color: string;
  badge: string;
  category: string;
} {
  const s = rel.toLowerCase();
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
    s.includes('love')
  ) {
    return {
      color: '#ec4899', // Pink
      badge: 'bg-pink-500/15 text-pink-300 border-pink-500/30',
      category: 'Family & Bond',
    };
  }
  if (
    s.includes('enemy') ||
    s.includes('rival') ||
    s.includes('nemesis') ||
    s.includes('hostile') ||
    s.includes('opponent') ||
    s.includes('foe')
  ) {
    return {
      color: '#ef4444', // Red
      badge: 'bg-red-500/15 text-red-300 border-red-500/30',
      category: 'Rival & Hostile',
    };
  }
  if (
    s.includes('ally') ||
    s.includes('friend') ||
    s.includes('comrade') ||
    s.includes('companion')
  ) {
    return {
      color: '#10b981', // Emerald
      badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
      category: 'Ally & Friend',
    };
  }
  if (
    s.includes('mentor') ||
    s.includes('master') ||
    s.includes('teacher') ||
    s.includes('disciple') ||
    s.includes('student') ||
    s.includes('servant') ||
    s.includes('lord')
  ) {
    return {
      color: '#f59e0b', // Amber
      badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
      category: 'Mentor & Order',
    };
  }
  return {
    color: '#818cf8', // Indigo
    badge: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    category: 'Acquaintance',
  };
}

export const CharacterVisualizer: React.FC<CharacterVisualizerProps> = ({
  characters,
  selectedCharacterIndex = 0,
  onSelectCharacter,
  onEditCharacter,
  onAddCharacter,
}) => {
  const [internalSelectedIndex, setInternalSelectedIndex] = useState<number>(
    selectedCharacterIndex ?? 0
  );
  const [viewMode, setViewMode] = useState<'dossier' | 'network'>('dossier');
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  // Keep internal index in sync if prop changes
  React.useEffect(() => {
    if (selectedCharacterIndex !== undefined && selectedCharacterIndex !== null) {
      setInternalSelectedIndex(selectedCharacterIndex);
    }
  }, [selectedCharacterIndex]);

  const activeIndex =
    characters.length > 0
      ? Math.min(Math.max(0, internalSelectedIndex), characters.length - 1)
      : 0;

  const activeChar = characters[activeIndex] as BibleCharacter | undefined;

  // Filtered characters for sidebar
  const filteredChars = useMemo(() => {
    return characters.filter((c) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        c.name.toLowerCase().includes(q) ||
        c.original_name.toLowerCase().includes(q) ||
        (c.role && c.role.toLowerCase().includes(q)) ||
        (c.aliases && c.aliases.some((a) => a.toLowerCase().includes(q)));

      const matchesRole =
        roleFilter === 'all'
          ? true
          : (c.role || 'minor').toLowerCase() === roleFilter.toLowerCase();

      return matchesSearch && matchesRole;
    });
  }, [characters, searchQuery, roleFilter]);

  const selectCharacterByIndex = (idx: number) => {
    setInternalSelectedIndex(idx);
    if (onSelectCharacter) onSelectCharacter(idx);
  };

  const selectCharacterByName = (name: string) => {
    const idx = characters.findIndex(
      (c) =>
        c.name.toLowerCase() === name.toLowerCase() ||
        c.original_name.toLowerCase() === name.toLowerCase() ||
        (c.aliases && c.aliases.some((a) => a.toLowerCase() === name.toLowerCase()))
    );
    if (idx !== -1) {
      selectCharacterByIndex(idx);
    }
  };

  // Build network graph data for the active character
  const personalRelationships = useMemo(() => {
    if (!activeChar) return [];
    const entries: {
      targetName: string;
      relation: string;
      targetChar?: BibleCharacter;
      targetIndex: number;
      categoryInfo: ReturnType<typeof getRelationshipCategory>;
    }[] = [];

    // Direct relationships defined on activeChar
    if (activeChar.relationships) {
      for (const [targetName, relation] of Object.entries(activeChar.relationships)) {
        const targetIndex = characters.findIndex(
          (c) =>
            c.name.toLowerCase() === targetName.toLowerCase() ||
            c.original_name.toLowerCase() === targetName.toLowerCase()
        );
        entries.push({
          targetName,
          relation,
          targetChar: targetIndex !== -1 ? characters[targetIndex] : undefined,
          targetIndex,
          categoryInfo: getRelationshipCategory(relation),
        });
      }
    }

    // Reverse relationships (where another character mentions activeChar)
    for (let i = 0; i < characters.length; i++) {
      if (i === activeIndex) continue;
      const other = characters[i];
      if (other.relationships) {
        for (const [tName, rel] of Object.entries(other.relationships)) {
          if (
            tName.toLowerCase() === activeChar.name.toLowerCase() ||
            tName.toLowerCase() === activeChar.original_name.toLowerCase()
          ) {
            // Only add if not already present
            if (!entries.some((e) => e.targetIndex === i)) {
              entries.push({
                targetName: other.name,
                relation: `Related (${rel})`,
                targetChar: other,
                targetIndex: i,
                categoryInfo: getRelationshipCategory(rel),
              });
            }
          }
        }
      }
    }

    return entries;
  }, [activeChar, activeIndex, characters]);

  if (characters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-12 text-center text-slate-400">
        <Users className="w-12 h-12 text-slate-600 mb-3 animate-pulse" />
        <h3 className="text-lg font-bold text-slate-200">No Characters Registered Yet</h3>
        <p className="text-xs text-slate-400 max-w-sm mt-1 mb-4">
          Add novel characters to the Bible or run the Entity Extractor agent on your chapters to discover them automatically!
        </p>
        {onAddCharacter && (
          <button
            onClick={onAddCharacter}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20 cursor-pointer transition-all"
          >
            <Plus className="w-4 h-4" />
            Add First Character
          </button>
        )}
      </div>
    );
  }

  const roleCfg = getRoleConfig(activeChar?.role);
  const RoleIcon = roleCfg.icon;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Visualizer Control Bar */}
      <div className="px-6 py-3 bg-slate-900/60 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Sparkles className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              Character Visualizer & Relationship Web
              <span className="text-[11px] px-2 py-0.2 rounded-full bg-slate-800 text-slate-400 font-mono">
                {characters.length} Registered
              </span>
            </h2>
            <p className="text-[11px] text-slate-400">
              Explore character identities, speech registers, dialogue rules & narrative connections.
            </p>
          </div>
        </div>

        {/* View Mode Toggle (Dossier vs Global Network) */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setViewMode('dossier')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              viewMode === 'dossier'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Character Dossier
          </button>
          <button
            onClick={() => setViewMode('network')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              viewMode === 'network'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Network className="w-3.5 h-3.5 text-amber-400" />
            Full Relationship Web
          </button>
        </div>
      </div>

      {/* Main Grid: Left Roster & Right Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Character Roster */}
        <div className="w-80 border-r border-slate-800/80 bg-slate-900/30 flex flex-col shrink-0">
          {/* Roster Search & Role Filters */}
          <div className="p-3 border-b border-slate-800/80 space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search characters or aliases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Role Filter Buttons */}
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5 text-[11px] no-scrollbar">
              {['all', 'protagonist', 'antagonist', 'supporting', 'mentor'].map((r) => (
                <button
                  key={r}
                  onClick={() => setRoleFilter(r)}
                  className={`px-2 py-0.5 rounded-md font-medium capitalize cursor-pointer transition-colors shrink-0 ${
                    roleFilter === r
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-950/80 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Roster Character List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40">
            {filteredChars.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No characters match the filter criteria.
              </div>
            ) : (
              filteredChars.map((c) => {
                const origIndex = characters.indexOf(c);
                const isSelected = origIndex === activeIndex;
                const rCfg = getRoleConfig(c.role);
                const RIcon = rCfg.icon;
                const relCount = c.relationships ? Object.keys(c.relationships).length : 0;

                return (
                  <div
                    key={origIndex}
                    onClick={() => selectCharacterByIndex(origIndex)}
                    className={`p-3 cursor-pointer transition-all flex items-center justify-between gap-3 select-none ${
                      isSelected
                        ? 'bg-indigo-950/50 border-l-4 border-indigo-500 shadow-sm'
                        : 'hover:bg-slate-900/60 border-l-4 border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      {/* Avatar Circle */}
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 shadow-inner ${
                          isSelected
                            ? 'bg-indigo-600 text-white ring-2 ring-indigo-400'
                            : 'bg-slate-800 text-slate-300 border border-slate-700'
                        }`}
                        style={{ borderColor: rCfg.color }}
                      >
                        {c.name.charAt(0).toUpperCase()}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-xs font-semibold truncate ${
                              isSelected ? 'text-indigo-200' : 'text-slate-200'
                            }`}
                          >
                            {c.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-400 truncate">
                          <span className="font-mono text-slate-500">{c.original_name}</span>
                          {c.role && (
                            <>
                              <span>&bull;</span>
                              <span className="capitalize">{c.role}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded border font-medium flex items-center gap-1 ${rCfg.badgeClass}`}
                      >
                        <RIcon className="w-2.5 h-2.5" />
                        {rCfg.label}
                      </span>
                      {relCount > 0 && (
                        <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                          <Share2 className="w-2.5 h-2.5" />
                          {relCount}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Visualization Canvas */}
        <div className="flex-1 flex flex-col overflow-y-auto bg-slate-950 p-6 space-y-6">
          {viewMode === 'dossier' && activeChar ? (
            /* DOSSIER VIEW MODE */
            <div className="space-y-6 max-w-5xl mx-auto w-full">
              {/* Hero Banner Card */}
              <div
                className={`relative overflow-hidden rounded-2xl border p-6 bg-gradient-to-br ${roleCfg.gradient} bg-slate-900/80 ${roleCfg.border} shadow-xl`}
              >
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative z-10">
                  <div className="flex items-center gap-4">
                    {/* Big Avatar */}
                    <div
                      className={`w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-black bg-slate-950/80 border-2 ${roleCfg.border} shadow-2xl ring-4 ${roleCfg.glow} text-white`}
                    >
                      {activeChar.name.charAt(0).toUpperCase()}
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h1 className="text-2xl font-black tracking-tight text-white">
                          {activeChar.name}
                        </h1>
                        <span className="text-base font-mono font-medium text-amber-300/90 px-2 py-0.5 rounded-lg bg-slate-950/60 border border-amber-500/20">
                          {activeChar.original_name}
                        </span>
                      </div>

                      {/* Attribute Pills */}
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-full border font-semibold flex items-center gap-1.5 ${roleCfg.badgeClass}`}
                        >
                          <RoleIcon className="w-3.5 h-3.5" />
                          {roleCfg.label}
                        </span>
                        {activeChar.gender && (
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-900/90 text-slate-300 border border-slate-800 capitalize">
                            {activeChar.gender}
                          </span>
                        )}
                        {activeChar.power_level && (
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                            <Zap className="w-3 h-3" />
                            {activeChar.power_level}
                          </span>
                        )}
                        {activeChar.status && (
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Status: {activeChar.status}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  {onEditCharacter && (
                    <button
                      onClick={() => onEditCharacter(activeChar, activeIndex)}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700/80 rounded-xl text-xs font-semibold cursor-pointer transition-colors shadow-sm"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-indigo-400" />
                      Edit Profile
                    </button>
                  )}
                </div>

                {/* Aliases Tag Cloud */}
                {activeChar.aliases && activeChar.aliases.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      Aliases & Titles:
                    </span>
                    {activeChar.aliases.map((alias, i) => (
                      <span
                        key={i}
                        className="text-xs px-2.5 py-0.5 rounded-md bg-slate-950/80 text-slate-300 border border-slate-800 shadow-inner font-medium"
                      >
                        {alias}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Middle Row: Dialogue Register & Speech Profile */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Voice & Speech Register Card */}
                <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-400 mb-3">
                      <MessageSquare className="w-4 h-4 text-indigo-400" />
                      Voice Register & Dialogue Directives
                    </div>

                    {activeChar.speaking_style || activeChar.voice ? (
                      <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 text-sm text-slate-200 italic leading-relaxed relative">
                        <span className="text-3xl text-indigo-500/30 absolute top-1 left-2 font-serif select-none">
                          &ldquo;
                        </span>
                        <p className="pl-4">
                          {activeChar.speaking_style || activeChar.voice}
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 italic">
                        No specific voice or tone register defined for this character yet.
                      </p>
                    )}
                  </div>

                  <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-1.5">
                    <Info className="w-3 h-3 text-slate-500" />
                    Injected into Context-Aware Drafter & Polishing Agent prompts.
                  </p>
                </div>

                {/* Pronouns & Address Forms Card */}
                <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-400 mb-3">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      Pronoun Mapping & Zero-Anaphora
                    </div>

                    {activeChar.pronouns ? (
                      typeof activeChar.pronouns === 'string' ? (
                        <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800 text-xs text-slate-300">
                          {activeChar.pronouns}
                        </div>
                      ) : (
                        <div className="space-y-2 bg-slate-950/70 p-3 rounded-xl border border-slate-800 text-xs">
                          {activeChar.pronouns.source && (
                            <div className="flex items-center justify-between">
                              <span className="text-slate-400">Source Pronouns:</span>
                              <span className="font-mono text-indigo-300 font-medium">
                                {activeChar.pronouns.source}
                              </span>
                            </div>
                          )}
                          {activeChar.pronouns.target && (
                            <div className="flex items-center justify-between">
                              <span className="text-slate-400">Target Translation:</span>
                              <span className="font-mono text-emerald-300 font-medium">
                                {activeChar.pronouns.target}
                              </span>
                            </div>
                          )}
                          {activeChar.pronouns.relational &&
                            Object.keys(activeChar.pronouns.relational).length > 0 && (
                              <div className="pt-2 border-t border-slate-800/80">
                                <span className="text-[11px] text-slate-400 block mb-1">
                                  Relational Pronouns:
                                </span>
                                {Object.entries(activeChar.pronouns.relational).map(([k, v]) => (
                                  <div
                                    key={k}
                                    className="flex items-center justify-between text-[11px] py-0.5"
                                  >
                                    <span className="text-slate-300">{k}</span>
                                    <span className="font-mono text-amber-300">{v}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                        </div>
                      )
                    ) : (
                      <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800/60 text-xs text-slate-500">
                        No custom pronouns configured. Using default {activeChar.gender || 'neutral'}{' '}
                        grammatical agreements.
                      </div>
                    )}
                  </div>

                  <p className="text-[11px] text-slate-400 mt-3 flex items-center gap-1.5">
                    <Info className="w-3 h-3 text-slate-500" />
                    Enforces pronoun consistency during high-speed zero-anaphora resolution.
                  </p>
                </div>
              </div>

              {/* Personal Relationship Network Visualization */}
              <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Network className="w-4 h-4 text-indigo-400" />
                    <h3 className="text-sm font-bold text-slate-200">
                      Personal Relationship Map ({personalRelationships.length})
                    </h3>
                  </div>
                  <span className="text-xs text-slate-500">
                    Click any connected character to inspect their dossier
                  </span>
                </div>

                {personalRelationships.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500 bg-slate-950/40 rounded-xl border border-slate-800/60 flex flex-col items-center gap-2">
                    <Share2 className="w-6 h-6 text-slate-600" />
                    <span>No relationships registered yet for this character.</span>
                    {onEditCharacter && (
                      <button
                        onClick={() => onEditCharacter(activeChar, activeIndex)}
                        className="mt-1 px-3 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg text-xs font-semibold cursor-pointer"
                      >
                        Add Relationships
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* SVG Radial Web Diagram */}
                    <div className="w-full bg-slate-950/80 rounded-xl border border-slate-800/80 p-4 flex items-center justify-center overflow-x-auto">
                      <svg
                        viewBox="0 0 500 320"
                        className="w-full max-w-lg h-auto select-none"
                        style={{ minWidth: '400px' }}
                      >
                        {/* Center Node: Active Character */}
                        <defs>
                          <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stopColor={roleCfg.color} stopOpacity="0.4" />
                            <stop offset="100%" stopColor={roleCfg.color} stopOpacity="0" />
                          </radialGradient>
                        </defs>

                        <circle cx={250} cy={160} r={55} fill="url(#centerGlow)" />

                        {/* Connections to related characters */}
                        {personalRelationships.map((rel, idx) => {
                          const total = personalRelationships.length;
                          const angle = (2 * Math.PI * idx) / total - Math.PI / 2;
                          const radius = 110;
                          const x = 250 + radius * Math.cos(angle);
                          const y = 160 + radius * Math.sin(angle);
                          const midX = (250 + x) / 2;
                          const midY = (160 + y) / 2;

                          return (
                            <g key={idx} className="group/line">
                              {/* Connector line */}
                              <line
                                x1={250}
                                y1={160}
                                x2={x}
                                y2={y}
                                stroke={rel.categoryInfo.color}
                                strokeWidth="2"
                                strokeDasharray="4 2"
                                className="opacity-70 group-hover/line:opacity-100 group-hover/line:stroke-width-3 transition-all"
                              />

                              {/* Relationship tag pill */}
                              <rect
                                x={midX - 35}
                                y={midY - 9}
                                width={70}
                                height={18}
                                rx={4}
                                fill="#020617"
                                stroke={rel.categoryInfo.color}
                                strokeWidth="1"
                                className="opacity-90 shadow"
                              />
                              <text
                                x={midX}
                                y={midY + 3.5}
                                textAnchor="middle"
                                fill={rel.categoryInfo.color}
                                fontSize="9"
                                fontWeight="bold"
                                className="select-none pointer-events-none font-mono"
                              >
                                {rel.relation.length > 11
                                  ? `${rel.relation.slice(0, 10)}…`
                                  : rel.relation}
                              </text>

                              {/* Outer Related Node */}
                              <g
                                onClick={() => {
                                  if (rel.targetIndex !== -1) {
                                    selectCharacterByIndex(rel.targetIndex);
                                  } else {
                                    selectCharacterByName(rel.targetName);
                                  }
                                }}
                                className="cursor-pointer group/node"
                              >
                                <circle
                                  cx={x}
                                  cy={y}
                                  r={22}
                                  fill="#0f172a"
                                  stroke={rel.categoryInfo.color}
                                  strokeWidth="2.5"
                                  className="group-hover/node:scale-110 transition-transform shadow-md"
                                />
                                <text
                                  x={x}
                                  y={y + 4}
                                  textAnchor="middle"
                                  fill="#ffffff"
                                  fontSize="11"
                                  fontWeight="bold"
                                  className="pointer-events-none select-none"
                                >
                                  {rel.targetName.charAt(0).toUpperCase()}
                                </text>

                                {/* Name below node */}
                                <text
                                  x={x}
                                  y={y + 35}
                                  textAnchor="middle"
                                  fill="#cbd5e1"
                                  fontSize="10"
                                  fontWeight="600"
                                  className="pointer-events-none select-none"
                                >
                                  {rel.targetName.length > 12
                                    ? `${rel.targetName.slice(0, 11)}…`
                                    : rel.targetName}
                                </text>
                              </g>
                            </g>
                          );
                        })}

                        {/* Center Active Character Node Circle */}
                        <circle
                          cx={250}
                          cy={160}
                          r={28}
                          fill="#020617"
                          stroke={roleCfg.color}
                          strokeWidth="3.5"
                          className="shadow-2xl"
                        />
                        <text
                          x={250}
                          y={165}
                          textAnchor="middle"
                          fill="#ffffff"
                          fontSize="14"
                          fontWeight="900"
                          className="pointer-events-none select-none"
                        >
                          {activeChar.name.charAt(0).toUpperCase()}
                        </text>
                      </svg>
                    </div>

                    {/* Interactive Relationship Cards Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                      {personalRelationships.map((rel, idx) => (
                        <div
                          key={idx}
                          onClick={() => {
                            if (rel.targetIndex !== -1) {
                              selectCharacterByIndex(rel.targetIndex);
                            } else {
                              selectCharacterByName(rel.targetName);
                            }
                          }}
                          className="bg-slate-950/70 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 p-3 rounded-xl flex items-center justify-between cursor-pointer transition-all group"
                        >
                          <div className="min-w-0 flex-1 pr-2">
                            <span className="text-xs font-semibold text-slate-200 group-hover:text-indigo-300 transition-colors truncate block">
                              {rel.targetName}
                            </span>
                            <span
                              className={`text-[10px] px-2 py-0.2 rounded font-mono mt-1 inline-block border ${rel.categoryInfo.badge}`}
                            >
                              {rel.relation}
                            </span>
                          </div>
                          <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Character Summary & Narrative Lore */}
              {activeChar.summary && (
                <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-5">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-400 mb-2">
                    <Info className="w-4 h-4 text-indigo-400" />
                    Narrative Summary & Lore Biography
                  </div>
                  <p className="text-sm leading-relaxed text-slate-300 whitespace-pre-line">
                    {activeChar.summary}
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* FULL RELATIONSHIP WEB MODE */
            <div className="space-y-6 max-w-6xl mx-auto w-full h-full flex flex-col">
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 flex-1 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                      <Network className="w-5 h-5 text-indigo-400" />
                      Global Character Ecosystem & Social Graph
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Visual map of all registered characters and directional connections across the novel.
                    </p>
                  </div>

                  {/* Legend */}
                  <div className="flex items-center gap-3 text-xs font-medium text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Protagonist
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Antagonist
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" /> Supporting
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> Mentor
                    </span>
                  </div>
                </div>

                {/* SVG Canvas for Global Network */}
                <div className="flex-1 bg-slate-950 rounded-xl border border-slate-800/80 p-4 flex items-center justify-center relative overflow-hidden">
                  <svg
                    viewBox="0 0 700 450"
                    className="w-full h-full select-none"
                    style={{ minHeight: '380px' }}
                  >
                    {/* Render global nodes in a circular formation */}
                    {characters.map((c, i) => {
                      const count = characters.length;
                      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
                      const cx = 350;
                      const cy = 225;
                      const r = Math.min(180, 70 + count * 14);
                      const x1 = cx + r * Math.cos(angle);
                      const y1 = cy + r * Math.sin(angle);

                      // Render connections for this character
                      const lines = [];
                      if (c.relationships) {
                        for (const [targetName, rel] of Object.entries(c.relationships)) {
                          const targetIdx = characters.findIndex(
                            (tc) =>
                              tc.name.toLowerCase() === targetName.toLowerCase() ||
                              tc.original_name.toLowerCase() === targetName.toLowerCase()
                          );
                          if (targetIdx !== -1 && targetIdx > i) {
                            const targetAngle = (2 * Math.PI * targetIdx) / count - Math.PI / 2;
                            const x2 = cx + r * Math.cos(targetAngle);
                            const y2 = cy + r * Math.sin(targetAngle);
                            const relCat = getRelationshipCategory(rel);

                            lines.push(
                              <g key={`${i}-${targetIdx}`}>
                                <line
                                  x1={x1}
                                  y1={y1}
                                  x2={x2}
                                  y2={y2}
                                  stroke={relCat.color}
                                  strokeWidth="2"
                                  strokeOpacity="0.6"
                                  strokeDasharray="4 2"
                                />
                                <rect
                                  x={(x1 + x2) / 2 - 25}
                                  y={(y1 + y2) / 2 - 8}
                                  width={50}
                                  height={16}
                                  rx={3}
                                  fill="#020617"
                                  stroke={relCat.color}
                                  strokeWidth="1"
                                />
                                <text
                                  x={(x1 + x2) / 2}
                                  y={(y1 + y2) / 2 + 3}
                                  textAnchor="middle"
                                  fill={relCat.color}
                                  fontSize="8"
                                  fontWeight="bold"
                                >
                                  {rel.length > 8 ? `${rel.slice(0, 7)}…` : rel}
                                </text>
                              </g>
                            );
                          }
                        }
                      }
                      return lines;
                    })}

                    {/* Nodes */}
                    {characters.map((c, i) => {
                      const count = characters.length;
                      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
                      const cx = 350;
                      const cy = 225;
                      const r = Math.min(180, 70 + count * 14);
                      const x = cx + r * Math.cos(angle);
                      const y = cy + r * Math.sin(angle);
                      const cRole = getRoleConfig(c.role);
                      const isSelected = i === activeIndex;

                      return (
                        <g
                          key={i}
                          onClick={() => {
                            selectCharacterByIndex(i);
                            setViewMode('dossier');
                          }}
                          className="cursor-pointer group/node"
                        >
                          <circle
                            cx={x}
                            cy={y}
                            r={isSelected ? 24 : 18}
                            fill="#090d16"
                            stroke={cRole.color}
                            strokeWidth={isSelected ? 3.5 : 2}
                            className="group-hover/node:scale-115 transition-transform"
                          />
                          <text
                            x={x}
                            y={y + (isSelected ? 5 : 4)}
                            textAnchor="middle"
                            fill="#ffffff"
                            fontSize={isSelected ? '12' : '10'}
                            fontWeight="bold"
                            className="pointer-events-none select-none"
                          >
                            {c.name.charAt(0).toUpperCase()}
                          </text>

                          {/* Character Name Label */}
                          <text
                            x={x}
                            y={y + 30}
                            textAnchor="middle"
                            fill={isSelected ? '#818cf8' : '#cbd5e1'}
                            fontSize="10"
                            fontWeight="bold"
                            className="pointer-events-none select-none"
                          >
                            {c.name.length > 10 ? `${c.name.slice(0, 9)}…` : c.name}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
