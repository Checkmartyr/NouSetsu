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
  Languages,
} from 'lucide-react';
import { BibleCharacter } from '../types/dashboard';
import {
  ObsidianRelationshipGraph,
  getEnhancedRelationshipCategory,
  RelationshipCategoryInfo,
} from './ObsidianRelationshipGraph';

interface CharacterVisualizerProps {
  characters: BibleCharacter[];
  selectedCharacterIndex?: number | null;
  onSelectCharacter?: (index: number) => void;
  onEditCharacter?: (char: BibleCharacter, index: number) => void;
  onAddCharacter?: () => void;
  sourceLanguage?: string;
  targetLanguage?: string;
}

// Role thematic configurations
const ROLE_CONFIGS: Record<
  string,
  {
    label: string;
    badgeClass: string;
    border: string;
    color: string;
    icon: React.FC<{ className?: string }>;
  }
> = {
  protagonist: {
    label: 'Protagonist',
    badgeClass: 'bg-[#383330] text-[#d9a05b] border-[#3f3a36]',
    border: 'border-[#d9a05b]/40',
    color: '#d9a05b',
    icon: Crown,
  },
  antagonist: {
    label: 'Antagonist',
    badgeClass: 'bg-[#383330] text-[#cf6659] border-[#3f3a36]',
    border: 'border-[#cf6659]/40',
    color: '#cf6659',
    icon: Swords,
  },
  supporting: {
    label: 'Supporting',
    badgeClass: 'bg-[#383330] text-[#8b9bb4] border-[#3f3a36]',
    border: 'border-[#8b9bb4]/40',
    color: '#8b9bb4',
    icon: Shield,
  },
  mentor: {
    label: 'Mentor',
    badgeClass: 'bg-[#383330] text-[#b0a89f] border-[#3f3a36]',
    border: 'border-[#b0a89f]/40',
    color: '#b0a89f',
    icon: Award,
  },
  minor: {
    label: 'Minor',
    badgeClass: 'bg-[#383330] text-[#857d75] border-[#3f3a36]',
    border: 'border-[#857d75]/40',
    color: '#857d75',
    icon: User,
  },
};

function getRoleConfig(role?: string) {
  const r = (role || 'minor').toLowerCase();
  return ROLE_CONFIGS[r] || ROLE_CONFIGS.minor;
}

// Relationship category detection (enhanced with multilingual Thai/CJK/English support)
function getRelationshipCategory(rel: string): RelationshipCategoryInfo {
  return getEnhancedRelationshipCategory(rel);
}

export const CharacterVisualizer: React.FC<CharacterVisualizerProps> = ({
  characters,
  selectedCharacterIndex = 0,
  onSelectCharacter,
  onEditCharacter,
  onAddCharacter,
  sourceLanguage,
  targetLanguage,
}) => {
  const [internalSelectedIndex, setInternalSelectedIndex] = useState<number>(
    selectedCharacterIndex ?? 0
  );
  const [viewMode, setViewMode] = useState<'dossier' | 'network'>('dossier');
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [relViewMode, setRelViewMode] = useState<'graph' | 'matrix'>('graph');
  const [matrixSearch, setMatrixSearch] = useState('');

  const activeIndex = selectedCharacterIndex ?? internalSelectedIndex;
  const activeChar = characters[activeIndex] || characters[0];

  const selectCharacterByIndex = (index: number) => {
    setInternalSelectedIndex(index);
    if (onSelectCharacter) {
      onSelectCharacter(index);
    }
  };

  const selectCharacterByName = (name: string) => {
    const idx = characters.findIndex(
      (c) =>
        c.name.toLowerCase() === name.toLowerCase() ||
        c.original_name.toLowerCase() === name.toLowerCase()
    );
    if (idx !== -1) {
      selectCharacterByIndex(idx);
    }
  };

  // Filtered characters for the roster
  const filteredChars = useMemo(() => {
    return characters.filter((c) => {
      const matchesSearch =
        !searchQuery.trim() ||
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.original_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.aliases && c.aliases.some((a) => a.toLowerCase().includes(searchQuery.toLowerCase())));

      const matchesRole =
        roleFilter === 'all' || (c.role && c.role.toLowerCase() === roleFilter.toLowerCase());

      return matchesSearch && matchesRole;
    });
  }, [characters, searchQuery, roleFilter]);

  // Personal relationships for active character
  const personalRelationships = useMemo(() => {
    if (!activeChar || !activeChar.relationships) return [];
    return Object.entries(activeChar.relationships).map(([targetName, relation]) => {
      const targetChar = characters.find(
        (c) =>
          c.name.toLowerCase() === targetName.toLowerCase() ||
          c.original_name.toLowerCase() === targetName.toLowerCase()
      );
      const targetIndex = targetChar ? characters.indexOf(targetChar) : -1;
      return {
        targetName,
        relation,
        targetChar,
        targetIndex,
        categoryInfo: getRelationshipCategory(relation),
      };
    });
  }, [activeChar, characters]);

  if (characters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center h-full bg-[#2b2622] text-[#f7f5f0] font-sans">
        <div className="w-12 h-12 rounded-[4px] bg-[#383330] border border-[#3f3a36] flex items-center justify-center text-[#b0a89f] mb-3">
          <Sparkles className="w-6 h-6 text-[#d9a05b]" />
        </div>
        <h3 className="text-sm font-semibold text-[#f7f5f0]">No Characters in Novel Bible</h3>
        <p className="text-xs text-[#857d75] max-w-sm mt-1 mb-4">
          Add characters to the Bible or run the Entity Extractor agent to discover them automatically.
        </p>
        {onAddCharacter && (
          <button
            onClick={onAddCharacter}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f7f5f0] hover:bg-[#e2ded6] text-[#2b2622] rounded-[3px] text-xs font-semibold cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add First Character
          </button>
        )}
      </div>
    );
  }

  const roleCfg = getRoleConfig(activeChar?.role);
  const RoleIcon = roleCfg.icon;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#2b2622] text-[#f7f5f0] font-sans">
      {/* Top Visualizer Control Bar */}
      <div className="px-5 py-2.5 bg-[#2b2622] border-b border-[#3f3a36] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-[3px] bg-[#383330] border border-[#3f3a36] text-[#d9a05b]">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-[#f7f5f0] flex items-center gap-2 font-mono uppercase tracking-wide">
              Character Visualizer
              <span className="text-[10px] px-1.5 py-0.2 rounded-[2px] bg-[#383330] text-[#857d75] border border-[#3f3a36]">
                {characters.length} Registered
              </span>
            </h2>
            <p className="text-[11px] text-[#857d75]">
              Explore character identities, speech registers, and narrative connections.
            </p>
          </div>
        </div>

        {/* View Mode Toggle (Dossier vs Global Network) */}
        <div className="flex items-center gap-0.5 bg-[#24201d] p-0.5 rounded-[3px] border border-[#3f3a36]">
          <button
            onClick={() => setViewMode('dossier')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] text-xs font-medium cursor-pointer transition-colors ${
              viewMode === 'dossier'
                ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                : 'text-[#b0a89f] hover:text-[#f7f5f0]'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Character Dossier
          </button>
          <button
            onClick={() => setViewMode('network')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] text-xs font-medium cursor-pointer transition-colors ${
              viewMode === 'network'
                ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                : 'text-[#b0a89f] hover:text-[#f7f5f0]'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            Relationship Web
          </button>
        </div>
      </div>

      {/* Main Grid: Left Roster & Right Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Character Roster */}
        <div className="w-72 border-r border-[#3f3a36] bg-[#2b2622] flex flex-col shrink-0">
          {/* Roster Search & Role Filters */}
          <div className="p-2.5 border-b border-[#3f3a36] space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#857d75]" />
              <input
                type="text"
                placeholder="Search characters or aliases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-2.5 py-1 text-xs bg-[#24201d] border border-[#3f3a36] rounded-[3px] text-[#f7f5f0] placeholder-[#857d75] focus:outline-none focus:border-[#b0a89f]"
              />
            </div>

            {/* Role Filter Buttons */}
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5 text-[10px] font-mono no-scrollbar">
              {['all', 'protagonist', 'antagonist', 'supporting', 'mentor'].map((r) => (
                <button
                  key={r}
                  onClick={() => setRoleFilter(r)}
                  className={`px-2 py-0.5 rounded-[2px] font-medium capitalize cursor-pointer transition-colors shrink-0 ${
                    roleFilter === r
                      ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                      : 'bg-[#24201d] text-[#857d75] hover:text-[#f7f5f0] border border-[#3f3a36]'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Roster Character List */}
          <div className="flex-1 overflow-y-auto divide-y divide-[#3f3a36]/50">
            {filteredChars.length === 0 ? (
              <div className="p-4 text-center text-xs text-[#857d75]">
                No matching characters.
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
                    className={`p-2.5 cursor-pointer transition-colors flex items-center justify-between gap-2.5 select-none ${
                      isSelected
                        ? 'bg-[#383330] border-l-2 border-[#f7f5f0]'
                        : 'hover:bg-[#383330]/40 border-l-2 border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      {/* Avatar Circle */}
                      <div
                        className={`w-7 h-7 rounded-[3px] flex items-center justify-center font-bold text-xs shrink-0 font-mono ${
                          isSelected
                            ? 'bg-[#f7f5f0] text-[#2b2622]'
                            : 'bg-[#24201d] text-[#b0a89f] border border-[#3f3a36]'
                        }`}
                        style={{ borderColor: isSelected ? undefined : rCfg.color }}
                      >
                        {c.name.charAt(0).toUpperCase()}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-xs font-semibold truncate ${
                              isSelected ? 'text-[#f7f5f0]' : 'text-[#b0a89f]'
                            }`}
                          >
                            {c.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 text-[10px] text-[#857d75] truncate font-mono">
                          <span>{c.original_name}</span>
                          {c.role && (
                            <>
                              <span>•</span>
                              <span className="capitalize">{c.role}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded-[2px] border font-mono flex items-center gap-1 ${rCfg.badgeClass}`}
                      >
                        <RIcon className="w-2.5 h-2.5" />
                        {rCfg.label}
                      </span>
                      {relCount > 0 && (
                        <span className="text-[10px] text-[#857d75] font-mono flex items-center gap-0.5">
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
        <div className="flex-1 flex flex-col overflow-y-auto bg-[#24201d] p-5 space-y-4">
          {viewMode === 'dossier' && activeChar ? (
            /* DOSSIER VIEW MODE */
            <div className="space-y-4 max-w-4xl mx-auto w-full">
              {/* Hero Banner Card */}
              <div className="rounded-[4px] border border-[#3f3a36] p-4 bg-[#383330]">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 relative z-10">
                  <div className="flex items-center gap-3">
                    {/* Big Avatar */}
                    <div
                      className="w-12 h-12 rounded-[4px] flex items-center justify-center text-xl font-bold bg-[#24201d] border border-[#3f3a36] text-[#f7f5f0] font-mono"
                      style={{ borderColor: roleCfg.color }}
                    >
                      {activeChar.name.charAt(0).toUpperCase()}
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h1 className="text-lg font-bold tracking-tight text-[#f7f5f0]">
                          {activeChar.name}
                        </h1>
                        <span className="text-xs font-mono text-[#d9a05b] px-1.5 py-0.5 rounded-[2px] bg-[#24201d] border border-[#3f3a36]">
                          {activeChar.original_name}
                        </span>
                      </div>

                      {/* Attribute Pills */}
                      <div className="flex flex-wrap items-center gap-1.5 mt-1.5 font-mono text-xs">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-[2px] border font-semibold flex items-center gap-1 ${roleCfg.badgeClass}`}
                        >
                          <RoleIcon className="w-3 h-3" />
                          {roleCfg.label}
                        </span>
                        {activeChar.gender && (
                          <span className="text-[10px] px-2 py-0.5 rounded-[2px] bg-[#24201d] text-[#b0a89f] border border-[#3f3a36] capitalize">
                            {activeChar.gender}
                          </span>
                        )}
                        {activeChar.power_level && (
                          <span className="text-[10px] px-2 py-0.5 rounded-[2px] bg-[#24201d] text-[#d9a05b] border border-[#3f3a36] flex items-center gap-1">
                            <Zap className="w-2.5 h-2.5" />
                            {activeChar.power_level}
                          </span>
                        )}
                        {activeChar.status && (
                          <span className="text-[10px] px-2 py-0.5 rounded-[2px] bg-[#24201d] text-[#7fa678] border border-[#3f3a36]">
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
                      className="flex items-center gap-1 px-2.5 py-1 bg-[#24201d] hover:bg-[#3f3a36] text-[#f7f5f0] border border-[#3f3a36] rounded-[3px] text-xs font-medium cursor-pointer transition-colors"
                    >
                      <Edit2 className="w-3 h-3 text-[#b0a89f]" />
                      Edit Profile
                    </button>
                  )}
                </div>

                {/* Aliases Tag Cloud */}
                {activeChar.aliases && activeChar.aliases.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-[#3f3a36] flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] font-mono text-[#857d75] uppercase tracking-wider">
                      Aliases:
                    </span>
                    {activeChar.aliases.map((alias, i) => (
                      <span
                        key={i}
                        className="text-[11px] font-mono px-2 py-0.5 rounded-[2px] bg-[#24201d] text-[#b0a89f] border border-[#3f3a36]"
                      >
                        {alias}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Linguistic Name Components (Source & Target) */}
              {activeChar.names && (
                Boolean(
                  activeChar.names.source && (activeChar.names.source.name || activeChar.names.source.m_name || activeChar.names.source.s_name)
                ) ||
                Boolean(
                  activeChar.names.target && (activeChar.names.target.name || activeChar.names.target.m_name || activeChar.names.target.s_name)
                )
              ) && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#b0a89f] font-mono">
                      <Languages className="w-3.5 h-3.5 text-[#d9a05b]" />
                      Linguistic Name Components
                    </div>
                    <span className="text-[10px] font-mono text-[#857d75]">
                      Structured Naming Model
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Source Script */}
                    <div className="bg-[#24201d] p-3 rounded-[3px] border border-[#3f3a36]">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-[#857d75] mb-2 flex items-center justify-between">
                        <span>{sourceLanguage || 'Source Script'}</span>
                        <span className="text-[9px] text-[#b0a89f]/60 font-mono">Original</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Given</span>
                          <span className="text-xs font-mono font-medium text-[#f7f5f0] truncate block" title={activeChar.names.source?.name}>
                            {activeChar.names.source?.name || '—'}
                          </span>
                        </div>
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Middle</span>
                          <span className="text-xs font-mono font-medium text-[#f7f5f0] truncate block" title={activeChar.names.source?.m_name}>
                            {activeChar.names.source?.m_name || '—'}
                          </span>
                        </div>
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Surname</span>
                          <span className="text-xs font-mono font-medium text-[#f7f5f0] truncate block" title={activeChar.names.source?.s_name}>
                            {activeChar.names.source?.s_name || '—'}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Target Script */}
                    <div className="bg-[#24201d] p-3 rounded-[3px] border border-[#3f3a36]">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-[#857d75] mb-2 flex items-center justify-between">
                        <span>{targetLanguage || 'Target Translation'}</span>
                        <span className="text-[9px] text-emerald-400/80 font-mono">English</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Given</span>
                          <span className="text-xs font-mono font-medium text-emerald-400 truncate block" title={activeChar.names.target?.name}>
                            {activeChar.names.target?.name || '—'}
                          </span>
                        </div>
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Middle</span>
                          <span className="text-xs font-mono font-medium text-emerald-400 truncate block" title={activeChar.names.target?.m_name}>
                            {activeChar.names.target?.m_name || '—'}
                          </span>
                        </div>
                        <div className="bg-[#2b2622] p-2 rounded-[2px] border border-[#3f3a36]/60">
                          <span className="text-[9px] font-mono uppercase text-[#857d75] block">Surname</span>
                          <span className="text-xs font-mono font-medium text-emerald-400 truncate block" title={activeChar.names.target?.s_name}>
                            {activeChar.names.target?.s_name || '—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Middle Row: Dialogue Register & Speech Profile */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Voice & Speech Register Card */}
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#b0a89f] mb-2.5 font-mono">
                      <MessageSquare className="w-3.5 h-3.5 text-[#b0a89f]" />
                      Voice Register & Directives
                    </div>

                    {activeChar.speaking_style || activeChar.voice ? (
                      <div className="bg-[#24201d] p-3 rounded-[3px] border border-[#3f3a36] text-xs text-[#f7f5f0] italic leading-relaxed">
                        &ldquo;{activeChar.speaking_style || activeChar.voice}&rdquo;
                      </div>
                    ) : (
                      <p className="text-xs text-[#857d75] italic">
                        No specific voice or tone register defined yet.
                      </p>
                    )}
                  </div>

                  <p className="text-[10px] text-[#857d75] mt-2.5 flex items-center gap-1 font-mono">
                    <Info className="w-3 h-3" />
                    Injected into Drafter & Polishing Agent prompts.
                  </p>
                </div>

                {/* Pronouns & Address Forms Card */}
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#b0a89f] mb-2.5 font-mono">
                      <Sparkles className="w-3.5 h-3.5 text-[#d9a05b]" />
                      Pronouns & Zero-Anaphora
                    </div>

                    {activeChar.pronouns ? (
                      typeof activeChar.pronouns === 'string' ? (
                        <div className="bg-[#24201d] p-2.5 rounded-[3px] border border-[#3f3a36] text-xs text-[#b0a89f] font-mono">
                          {activeChar.pronouns}
                        </div>
                      ) : (
                        <div className="space-y-1.5 bg-[#24201d] p-2.5 rounded-[3px] border border-[#3f3a36] text-xs font-mono">
                          {activeChar.pronouns.source && (
                            <div className="flex items-center justify-between">
                              <span className="text-[#857d75]">Source:</span>
                              <span className="text-[#8b9bb4]">
                                {activeChar.pronouns.source}
                              </span>
                            </div>
                          )}
                          {activeChar.pronouns.target && (
                            <div className="flex items-center justify-between">
                              <span className="text-[#857d75]">Target:</span>
                              <span className="text-[#7fa678]">
                                {activeChar.pronouns.target}
                              </span>
                            </div>
                          )}
                        </div>
                      )
                    ) : (
                      <div className="bg-[#24201d] p-3 rounded-[3px] border border-[#3f3a36] text-xs text-[#857d75]">
                        Default {activeChar.gender || 'neutral'} agreement.
                      </div>
                    )}
                  </div>

                  <p className="text-[10px] text-[#857d75] mt-2.5 flex items-center gap-1 font-mono">
                    <Info className="w-3 h-3" />
                    Enforces consistency during zero-anaphora resolution.
                  </p>
                </div>
              </div>

              {/* Personal Relationship Network Visualization */}
              <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4">
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-[#f7f5f0] uppercase tracking-wide">
                    <Network className="w-3.5 h-3.5 text-[#b0a89f]" />
                    <span>Personal Relationship Map ({personalRelationships.length})</span>
                  </div>

                  {/* Mode Toggle: Obsidian Graph vs Categorized Cards */}
                  <div className="flex items-center gap-1 bg-[#24201d] p-0.5 rounded-[3px] border border-[#3f3a36] text-[11px] font-mono">
                    <button
                      onClick={() => setRelViewMode('graph')}
                      className={`px-2.5 py-1 rounded-[2px] transition-colors cursor-pointer flex items-center gap-1.5 ${
                        relViewMode === 'graph'
                          ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                          : 'text-[#857d75] hover:text-[#f7f5f0]'
                      }`}
                    >
                      <Sparkles className="w-3 h-3 text-[#d9a05b]" />
                      Obsidian Graph
                    </button>
                    <button
                      onClick={() => setRelViewMode('matrix')}
                      className={`px-2.5 py-1 rounded-[2px] transition-colors cursor-pointer flex items-center gap-1.5 ${
                        relViewMode === 'matrix'
                          ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold'
                          : 'text-[#857d75] hover:text-[#f7f5f0]'
                      }`}
                    >
                      <Compass className="w-3 h-3" />
                      Cards Matrix
                    </button>
                  </div>
                </div>

                {personalRelationships.length === 0 ? (
                  <div className="p-6 text-center text-xs text-[#857d75] bg-[#24201d] rounded-[3px] border border-[#3f3a36] flex flex-col items-center gap-1.5">
                    <Share2 className="w-5 h-5 text-[#857d75]" />
                    <span>No relationships registered yet for this character.</span>
                  </div>
                ) : relViewMode === 'graph' ? (
                  <div className="space-y-2">
                    <ObsidianRelationshipGraph
                      centerCharacter={activeChar}
                      relationships={personalRelationships}
                      onSelectCharacterByIndex={selectCharacterByIndex}
                      onSelectCharacterByName={selectCharacterByName}
                    />
                    <div className="flex items-center justify-between text-[10px] text-[#857d75] font-mono px-1">
                      <span>• Drag nodes to play with spring physics • Scroll to zoom • Drag canvas to pan</span>
                      <span>Click any node to inspect dossier</span>
                    </div>
                  </div>
                ) : (
                  /* Categorized Cards Matrix Mode */
                  <div className="space-y-4">
                    {/* Matrix search input */}
                    <div className="relative max-w-sm">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#857d75]" />
                      <input
                        type="text"
                        value={matrixSearch}
                        onChange={(e) => setMatrixSearch(e.target.value)}
                        placeholder="Search relationships..."
                        className="w-full pl-9 pr-4 py-1.5 bg-[#24201d] border border-[#3f3a36] focus:border-[#d9a05b] rounded-[3px] text-xs font-mono text-[#f7f5f0] placeholder-[#857d75] focus:outline-none"
                      />
                    </div>

                    {/* Grouped Category Sections */}
                    {(['ally', 'rival', 'family', 'mentor', 'acquaintance'] as const).map((catId) => {
                      const groupRels = personalRelationships.filter((r) => {
                        if (r.categoryInfo.id !== catId) return false;
                        if (matrixSearch) {
                          const q = matrixSearch.toLowerCase();
                          return (
                            r.targetName.toLowerCase().includes(q) ||
                            r.relation.toLowerCase().includes(q)
                          );
                        }
                        return true;
                      });

                      if (groupRels.length === 0) return null;
                      const sample = groupRels[0];

                      return (
                        <div key={catId} className="space-y-2">
                          <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#b0a89f]">
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: sample.categoryInfo.color }}
                            />
                            <span>{sample.categoryInfo.category}</span>
                            <span className="text-[10px] text-[#857d75] font-normal">
                              ({groupRels.length})
                            </span>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                            {groupRels.map((rel, idx) => (
                              <div
                                key={idx}
                                onClick={() => {
                                  if (rel.targetIndex !== -1) {
                                    selectCharacterByIndex(rel.targetIndex);
                                  } else {
                                    selectCharacterByName(rel.targetName);
                                  }
                                }}
                                className="bg-[#24201d] hover:bg-[#2b2622] border border-[#3f3a36] p-2.5 rounded-[3px] flex items-center justify-between cursor-pointer transition-colors group"
                              >
                                <div className="min-w-0 flex-1 pr-2">
                                  <span className="text-xs font-semibold text-[#f7f5f0] truncate block">
                                    {rel.targetName}
                                  </span>
                                  <span
                                    className={`text-[9px] px-1.5 py-0.2 rounded-[2px] font-mono mt-0.5 inline-block border ${rel.categoryInfo.badge}`}
                                  >
                                    {rel.relation}
                                  </span>
                                </div>
                                <ArrowRight className="w-3.5 h-3.5 text-[#857d75] group-hover:text-[#f7f5f0] transition-colors" />
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Character Summary & Narrative Lore */}
              {activeChar.summary && (
                <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#b0a89f] mb-2 font-mono">
                    <Info className="w-3.5 h-3.5 text-[#b0a89f]" />
                    Narrative Summary & Lore
                  </div>
                  <p className="text-xs leading-relaxed text-[#b0a89f] whitespace-pre-line">
                    {activeChar.summary}
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* FULL RELATIONSHIP WEB MODE */
            <div className="space-y-4 max-w-5xl mx-auto w-full h-full flex flex-col">
              <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-4 flex-1 flex flex-col">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-xs font-bold text-[#f7f5f0] flex items-center gap-1.5 font-mono uppercase tracking-wide">
                      <Network className="w-3.5 h-3.5 text-[#b0a89f]" />
                      Global Character Ecosystem & Graph
                    </h3>
                    <p className="text-[11px] text-[#857d75] mt-0.5">
                      Visual map of all registered characters and connections.
                    </p>
                  </div>

                  {/* Legend */}
                  <div className="flex items-center gap-2.5 text-[10px] font-mono text-[#857d75]">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-[1px] bg-[#d9a05b]" /> Protagonist
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-[1px] bg-[#cf6659]" /> Antagonist
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-[1px] bg-[#8b9bb4]" /> Supporting
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-[1px] bg-[#b0a89f]" /> Mentor
                    </span>
                  </div>
                </div>

                {/* SVG Canvas for Global Network */}
                <div className="flex-1 bg-[#24201d] rounded-[3px] border border-[#3f3a36] p-4 flex items-center justify-center relative overflow-hidden">
                  <svg
                    viewBox="0 0 700 450"
                    className="w-full h-full select-none"
                    style={{ minHeight: '350px' }}
                  >
                    {/* Render connections */}
                    {characters.map((c, i) => {
                      const count = characters.length;
                      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
                      const cx = 350;
                      const cy = 225;
                      const r = Math.min(180, 70 + count * 14);
                      const x1 = cx + r * Math.cos(angle);
                      const y1 = cy + r * Math.sin(angle);

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
                                  strokeWidth="1.5"
                                  strokeOpacity="0.5"
                                  strokeDasharray="3 3"
                                />
                                <rect
                                  x={(x1 + x2) / 2 - 22}
                                  y={(y1 + y2) / 2 - 7}
                                  width={44}
                                  height={14}
                                  rx={2}
                                  fill="#24201d"
                                  stroke={relCat.color}
                                  strokeWidth="0.8"
                                />
                                <text
                                  x={(x1 + x2) / 2}
                                  y={(y1 + y2) / 2 + 3}
                                  textAnchor="middle"
                                  fill={relCat.color}
                                  fontSize="8"
                                  fontWeight="bold"
                                  className="font-mono"
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
                          className="cursor-pointer"
                        >
                          <circle
                            cx={x}
                            cy={y}
                            r={isSelected ? 20 : 16}
                            fill={isSelected ? '#383330' : '#2b2622'}
                            stroke={cRole.color}
                            strokeWidth={isSelected ? 2.5 : 1.5}
                          />
                          <text
                            x={x}
                            y={y + 4}
                            textAnchor="middle"
                            fill="#f7f5f0"
                            fontSize="10"
                            fontWeight="bold"
                            className="pointer-events-none select-none font-mono"
                          >
                            {c.name.charAt(0).toUpperCase()}
                          </text>

                          {/* Character Name Label */}
                          <text
                            x={x}
                            y={y + 26}
                            textAnchor="middle"
                            fill={isSelected ? '#f7f5f0' : '#857d75'}
                            fontSize="9"
                            fontWeight="bold"
                            className="pointer-events-none select-none font-mono"
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
