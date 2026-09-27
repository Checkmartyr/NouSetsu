import React, { useState, useEffect } from 'react';
import {
  Users,
  BookMarked,
  Layers,
  Code,
  Plus,
  Trash2,
  Save,
  Search,
  Edit2,
  Check,
  X,
  Sparkles,
  BookOpen,
  Eye,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Target,
  CheckCircle2,
  Bookmark
} from 'lucide-react';
import { BibleData, BibleCharacter, BibleTerm, BibleArc } from '../types/dashboard';
import {
  fetchBible,
  updateBible,
  fetchRawBible,
  updateRawBible
} from '../services/dashboardApi';
import { CharacterVisualizer } from './CharacterVisualizer';
import { Pagination } from './Pagination';

interface BibleViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
}

type BibleTab = 'characters' | 'visualizer' | 'glossary' | 'memory' | 'raw';

export const BibleView: React.FC<BibleViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
}) => {
  const [activeTab, setActiveTab] = useState<BibleTab>('characters');
  const [bible, setBible] = useState<BibleData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Selected character for visualizer
  const [selectedCharIndex, setSelectedCharIndex] = useState<number | null>(0);

  // Raw YAML Mode
  const [rawYaml, setRawYaml] = useState('');
  const [loadingRaw, setLoadingRaw] = useState(false);

  // Search & Filter
  const [searchChar, setSearchChar] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [termCategoryFilter, setTermCategoryFilter] = useState('all');

  // Pagination State
  const [charPage, setCharPage] = useState(1);
  const [charPageSize, setCharPageSize] = useState(12);
  const [glossaryPage, setGlossaryPage] = useState(1);
  const [glossaryPageSize, setGlossaryPageSize] = useState(25);

  // Character Modal / Form
  const [isCharModalOpen, setIsCharModalOpen] = useState(false);
  const [editingCharIndex, setEditingCharIndex] = useState<number | null>(null);
  const [aliasesInput, setAliasesInput] = useState('');
  const [relationshipsInput, setRelationshipsInput] = useState('');
  const [charForm, setCharForm] = useState<BibleCharacter>({
    name: '',
    original_name: '',
    names: {
      source: { name: '', m_name: '', s_name: '' },
      target: { name: '', m_name: '', s_name: '' },
    },
    gender: 'female',
    role: '',
    speaking_style: '',
    power_level: '',
    status: '',
    summary: '',
  });

  // Glossary Modal / Form
  const [isTermModalOpen, setIsTermModalOpen] = useState(false);
  const [editingTermIndex, setEditingTermIndex] = useState<number | null>(null);
  const [termForm, setTermForm] = useState<BibleTerm>({
    term: '',
    translation: '',
    category: 'term',
    notes: '',
  });

  // Narrative Story Arcs State
  const [expandedArcIndices, setExpandedArcIndices] = useState<Set<number>>(new Set());
  const [activeArcExpanded, setActiveArcExpanded] = useState<boolean>(true);
  const [selectedArcModal, setSelectedArcModal] = useState<BibleArc | null>(null);
  const [searchArc, setSearchArc] = useState('');

  const toggleArcExpanded = (index: number) => {
    setExpandedArcIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const expandAllArcs = (count: number) => {
    setExpandedArcIndices(new Set(Array.from({ length: count }, (_, i) => i)));
  };

  const collapseAllArcs = () => {
    setExpandedArcIndices(new Set());
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const loadBibleData = async () => {
    if (!activeProjectPath) return;
    setLoading(true);
    const data = await fetchBible(activeProjectPath);
    setBible(data);
    setLoading(false);
  };

  const loadRawYamlData = async () => {
    if (!activeProjectPath) return;
    setLoadingRaw(true);
    const data = await fetchRawBible(activeProjectPath);
    if (data) setRawYaml(data.raw_yaml);
    setLoadingRaw(false);
  };

  useEffect(() => {
    loadBibleData();
    setCharPage(1);
    setGlossaryPage(1);
  }, [activeProjectPath]);

  useEffect(() => {
    setCharPage(1);
  }, [searchChar]);

  useEffect(() => {
    setGlossaryPage(1);
  }, [searchTerm, termCategoryFilter]);

  useEffect(() => {
    if (activeTab === 'raw') {
      loadRawYamlData();
    }
  }, [activeTab, activeProjectPath]);

  const handleSaveBible = async (updated: BibleData) => {
    if (!activeProjectPath) return;
    setSaving(true);
    const success = await updateBible(updated, activeProjectPath);
    setSaving(false);
    if (success) {
      setBible(updated);
      showToast('Bible saved successfully!');
    } else {
      alert('Failed to save Bible');
    }
  };

  const handleSaveRawYaml = async () => {
    if (!activeProjectPath) return;
    setSaving(true);
    const success = await updateRawBible(rawYaml, activeProjectPath);
    setSaving(false);
    if (success) {
      showToast('Raw bible.yaml saved successfully!');
      loadBibleData();
    } else {
      alert('Failed to save raw YAML');
    }
  };

  // Helper to parse name components from a full string
  const parseNameParts = (str?: string) => {
    if (!str) return { name: '', m_name: '', s_name: '' };
    const parts = str.split(/[・·\s]+/).filter(Boolean);
    if (parts.length === 1) return { name: parts[0], m_name: '', s_name: '' };
    if (parts.length === 2) return { name: parts[0], m_name: '', s_name: parts[1] };
    if (parts.length >= 3)
      return {
        name: parts[0],
        m_name: parts.slice(1, -1).join(' '),
        s_name: parts[parts.length - 1],
      };
    return { name: '', m_name: '', s_name: '' };
  };

  // Helper to assemble full name from components
  const assembleFullName = (
    detail?: { name?: string; m_name?: string; s_name?: string },
    isSource: boolean = false
  ) => {
    if (!detail) return '';
    const parts = [detail.name, detail.m_name, detail.s_name].filter(
      (p) => p && p.trim()
    ) as string[];
    if (parts.length === 0) return '';
    const isCjk = parts.some((p) => /[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]/.test(p));
    const sep = isCjk || isSource ? '・' : ' ';
    return parts.join(sep);
  };

  // Character Operations
  const openAddCharModal = () => {
    setEditingCharIndex(null);
    setCharForm({
      name: '',
      original_name: '',
      names: {
        source: { name: '', m_name: '', s_name: '' },
        target: { name: '', m_name: '', s_name: '' },
      },
      gender: 'unknown',
      role: 'supporting',
      speaking_style: '',
      power_level: '',
      status: 'active',
      summary: '',
      aliases: [],
      relationships: {},
    });
    setAliasesInput('');
    setRelationshipsInput('');
    setIsCharModalOpen(true);
  };

  const openEditCharModal = (char: BibleCharacter, index: number) => {
    setEditingCharIndex(index);
    const existingNames = char.names || {
      source: parseNameParts(char.original_name),
      target: parseNameParts(char.name),
    };
    setCharForm({
      ...char,
      names: {
        source: {
          name: existingNames.source?.name || '',
          m_name: existingNames.source?.m_name || '',
          s_name: existingNames.source?.s_name || '',
        },
        target: {
          name: existingNames.target?.name || '',
          m_name: existingNames.target?.m_name || '',
          s_name: existingNames.target?.s_name || '',
        },
      },
      speaking_style: char.speaking_style || char.voice || '',
      voice: char.voice || char.speaking_style || '',
    });
    setAliasesInput((char.aliases || []).join(', '));
    const relStr = char.relationships
      ? Object.entries(char.relationships)
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ')
      : '';
    setRelationshipsInput(relStr);
    setIsCharModalOpen(true);
  };

  const saveCharModal = () => {
    if (!bible) return;
    const parsedAliases = aliasesInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const parsedRelationships: Record<string, string> = {};
    if (relationshipsInput.trim()) {
      relationshipsInput.split(',').forEach((part) => {
        const [k, v] = part.split(':');
        if (k && v) {
          parsedRelationships[k.trim()] = v.trim();
        }
      });
    }

    const finalCharForm: BibleCharacter = {
      ...charForm,
      name: charForm.name.trim() || assembleFullName(charForm.names?.target, false) || 'Unnamed',
      original_name:
        charForm.original_name.trim() || assembleFullName(charForm.names?.source, true) || 'Unknown',
      aliases: parsedAliases,
      relationships: parsedRelationships,
      speaking_style: charForm.speaking_style || charForm.voice || '',
      voice: charForm.voice || charForm.speaking_style || '',
    };
    const newChars = [...bible.characters];
    if (editingCharIndex !== null) {
      newChars[editingCharIndex] = finalCharForm;
    } else {
      newChars.push(finalCharForm);
    }
    const updated = { ...bible, characters: newChars };
    handleSaveBible(updated);
    setIsCharModalOpen(false);
  };

  const deleteChar = (index: number) => {
    if (!bible || !confirm('Are you sure you want to delete this character?')) return;
    const newChars = bible.characters.filter((_, i) => i !== index);
    handleSaveBible({ ...bible, characters: newChars });
  };

  // Glossary Operations
  const openAddTermModal = () => {
    setEditingTermIndex(null);
    setTermForm({ term: '', translation: '', source: '', target: '', category: 'term', notes: '' });
    setIsTermModalOpen(true);
  };

  const openEditTermModal = (term: BibleTerm, index: number) => {
    setEditingTermIndex(index);
    setTermForm({
      ...term,
      term: term.term || term.source || '',
      translation: term.translation || term.target || '',
      source: term.source || term.term || '',
      target: term.target || term.translation || '',
    });
    setIsTermModalOpen(true);
  };

  const saveTermModal = () => {
    if (!bible) return;
    const finalTermForm: BibleTerm = {
      ...termForm,
      term: termForm.term || termForm.source || '',
      translation: termForm.translation || termForm.target || '',
      source: termForm.source || termForm.term || '',
      target: termForm.target || termForm.translation || '',
    };
    const newGlossary = [...bible.glossary];
    if (editingTermIndex !== null) {
      newGlossary[editingTermIndex] = finalTermForm;
    } else {
      newGlossary.push(finalTermForm);
    }
    const updated = { ...bible, glossary: newGlossary };
    handleSaveBible(updated);
    setIsTermModalOpen(false);
  };

  const deleteTerm = (index: number) => {
    if (!bible || !confirm('Are you sure you want to delete this term?')) return;
    const newGlossary = bible.glossary.filter((_, i) => i !== index);
    handleSaveBible({ ...bible, glossary: newGlossary });
  };

  // Filtered lists with original index preservation
  const filteredChars = (bible?.characters || [])
    .map((c, origIdx) => ({ c, origIdx }))
    .filter(({ c }) => {
      const q = searchChar.toLowerCase();
      return (
        c.name.toLowerCase().includes(q) ||
        c.original_name.toLowerCase().includes(q) ||
        (c.role && c.role.toLowerCase().includes(q))
      );
    });

  const charTotalPages = Math.max(1, Math.ceil(filteredChars.length / charPageSize));
  const safeCharPage = Math.min(Math.max(1, charPage), charTotalPages);
  const paginatedChars = filteredChars.slice(
    (safeCharPage - 1) * charPageSize,
    safeCharPage * charPageSize
  );

  const categories = Array.from(
    new Set((bible?.glossary || []).map((t) => t.category).filter(Boolean))
  ) as string[];

  const filteredGlossary = (bible?.glossary || [])
    .map((t, origIdx) => ({ t, origIdx }))
    .filter(({ t }) => {
      const q = searchTerm.toLowerCase();
      const termVal = (t.source || t.term || '').toLowerCase();
      const transVal = (t.target || t.translation || '').toLowerCase();
      const matchesSearch = termVal.includes(q) || transVal.includes(q);
      const matchesCat =
        termCategoryFilter === 'all' ? true : t.category === termCategoryFilter;
      return matchesSearch && matchesCat;
    });

  const glossaryTotalPages = Math.max(1, Math.ceil(filteredGlossary.length / glossaryPageSize));
  const safeGlossaryPage = Math.min(Math.max(1, glossaryPage), glossaryTotalPages);
  const paginatedGlossary = filteredGlossary.slice(
    (safeGlossaryPage - 1) * glossaryPageSize,
    safeGlossaryPage * glossaryPageSize
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#2b2622] text-[#f7f5f0]">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-16 right-8 z-50 px-3.5 py-1.5 bg-[#383330] text-[#f7f5f0] border border-[#3f3a36] rounded-[4px] shadow-lg text-xs font-medium flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header & Subnav */}
      <div className="bg-[#2b2622] border-b border-[#3f3a36] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <BookMarked className="w-4 h-4 text-[#dad2c1]" />
            <h1 className="text-base font-medium tracking-[-0.3px] text-[#f7f5f0]">
              Novel Bible: {bible?.title || activeProjectTitle || 'Series Memory'}
            </h1>
            {bible?.genre && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-[2px] bg-[#383330] text-[#dad2c1] border border-[#3f3a36]">
                {bible.genre}
              </span>
            )}
          </div>
          <p className="text-xs text-[#aea69c] mt-0.5">
            Canonical terminology, character profiles, voice registers & narrative lore
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-0.5 bg-[#2b2622] p-0.5 rounded-[4px] border border-[#3f3a36] max-w-full overflow-x-auto">
          <button
            onClick={() => setActiveTab('characters')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'characters'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Characters ({bible?.characters?.length ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('visualizer')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'visualizer'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-[#dad2c1]" />
            <span>Visualizer</span>
          </button>
          <button
            onClick={() => setActiveTab('glossary')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'glossary'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Glossary ({bible?.glossary?.length ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('memory')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'memory'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Narrative Memory</span>
          </button>
          <button
            onClick={() => setActiveTab('raw')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] text-xs transition-colors cursor-pointer ${
              activeTab === 'raw'
                ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>Raw YAML</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-6 bg-[#2b2622]">
        {loading ? (
          <div className="text-center py-20 text-[#aea69c] text-xs font-mono">Loading Bible data...</div>
        ) : activeTab === 'visualizer' ? (
          /* CHARACTER VISUALIZER VIEW */
          <div className="h-full -m-6 flex flex-col overflow-hidden">
            <CharacterVisualizer
              characters={bible?.characters || []}
              selectedCharacterIndex={selectedCharIndex ?? 0}
              onSelectCharacter={(idx) => setSelectedCharIndex(idx)}
              onEditCharacter={(c, idx) => openEditCharModal(c, idx)}
              onAddCharacter={openAddCharModal}
              sourceLanguage={bible?.source_language}
              targetLanguage={bible?.target_language}
            />
          </div>
        ) : activeTab === 'characters' ? (
          /* CHARACTERS VIEW */
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="relative flex-1 max-w-md">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#aea69c]" />
                <input
                  type="text"
                  placeholder="Search characters by name or role..."
                  value={searchChar}
                  onChange={(e) => setSearchChar(e.target.value)}
                  className="input-text w-full pl-9 pr-3 py-1.5 text-xs"
                />
              </div>

              <button
                onClick={openAddCharModal}
                className="btn-primary text-xs flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Character</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
              {paginatedChars.map(({ c, origIdx }) => (
                <div
                  key={origIdx}
                  className="bg-[#383330] border border-[#3f3a36] hover:border-[#544d47] rounded-[4px] p-4 flex flex-col justify-between transition-colors"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h2 className="text-sm font-medium text-[#f7f5f0]">{c.name}</h2>
                        <span className="text-xs text-[#aea69c] font-mono">
                          {c.original_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            setSelectedCharIndex(origIdx);
                            setActiveTab('visualizer');
                          }}
                          title="Visualize Character Sheet & Network"
                          aria-label={`Visualize ${c.name}`}
                          className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => openEditCharModal(c, origIdx)}
                          title="Edit"
                          aria-label={`Edit ${c.name}`}
                          className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer transition-colors"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => deleteChar(origIdx)}
                          title="Delete"
                          aria-label={`Delete ${c.name}`}
                          className="p-1 text-[#aea69c] hover:text-rose-400 cursor-pointer transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1 mt-2">
                      {c.gender && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#aea69c] border border-[#3f3a36]">
                          {c.gender}
                        </span>
                      )}
                      {c.role && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#dad2c1] border border-[#3f3a36]">
                          {c.role}
                        </span>
                      )}
                      {c.power_level && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-amber-300 border border-amber-800/40">
                          {c.power_level}
                        </span>
                      )}
                      {c.relationships && Object.keys(c.relationships).length > 0 && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#c9c0ad] border border-[#3f3a36]">
                          {Object.keys(c.relationships).length} links
                        </span>
                      )}
                    </div>

                    {c.names && (c.names.target?.name || c.names.target?.s_name || c.names.source?.name || c.names.source?.s_name) && (
                      <div className="text-[10px] font-mono px-2 py-1 mt-2 bg-[#24201d] rounded-[3px] border border-[#3f3a36] text-[#aea69c] flex flex-wrap gap-x-2 gap-y-0.5">
                        <span className="text-[#dad2c1] font-semibold">Names:</span>
                        {(c.names.target?.name || c.names.source?.name) && (
                          <span>Given: <strong className="text-[#f7f5f0]">{c.names.target?.name || c.names.source?.name}</strong></span>
                        )}
                        {(c.names.target?.m_name || c.names.source?.m_name) && (
                          <span>Mid: <strong className="text-[#f7f5f0]">{c.names.target?.m_name || c.names.source?.m_name}</strong></span>
                        )}
                        {(c.names.target?.s_name || c.names.source?.s_name) && (
                          <span>Sur: <strong className="text-[#f7f5f0]">{c.names.target?.s_name || c.names.source?.s_name}</strong></span>
                        )}
                      </div>
                    )}

                    {(c.speaking_style || c.voice) && (
                      <p className="text-xs text-[#aea69c] mt-2 italic">
                        &ldquo;{c.speaking_style || c.voice}&rdquo;
                      </p>
                    )}

                    {c.summary && (
                      <p className="text-xs text-[#dad2c1] mt-2 line-clamp-3">
                        {c.summary}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {filteredChars.length === 0 && (
              <div className="text-center py-12 text-[#aea69c] text-xs font-mono">
                {searchChar
                  ? `No characters found matching "${searchChar}".`
                  : 'No characters registered in Novel Bible yet.'}
              </div>
            )}

            <Pagination
              currentPage={safeCharPage}
              totalPages={charTotalPages}
              totalItems={filteredChars.length}
              pageSize={charPageSize}
              pageSizeOptions={[12, 24, 48]}
              onPageChange={setCharPage}
              onPageSizeChange={(newSize) => {
                setCharPageSize(newSize);
                setCharPage(1);
              }}
              itemName="characters"
            />
          </div>
        ) : activeTab === 'glossary' ? (
          /* GLOSSARY VIEW */
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 flex-1 max-w-lg">
                <div className="relative flex-1">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#aea69c]" />
                  <input
                    type="text"
                    placeholder="Search terms or translations..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="input-text w-full pl-9 pr-3 py-1.5 text-xs"
                  />
                </div>
                <select
                  value={termCategoryFilter}
                  onChange={(e) => setTermCategoryFilter(e.target.value)}
                  aria-label="Filter glossary by category"
                  className="bg-[#383330] border border-[#3f3a36] rounded-[3px] px-2.5 py-1.5 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#dad2c1]"
                >
                  <option value="all">All Categories</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={openAddTermModal}
                className="btn-primary text-xs flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Term</span>
              </button>
            </div>

            <div className="border border-[#3f3a36] rounded-[4px] overflow-hidden bg-[#383330]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#2b2622] border-b border-[#3f3a36] text-[#dad2c1] font-mono text-[11px] uppercase tracking-wider">
                    <th className="p-3">Source Term</th>
                    <th className="p-3">Standard Translation</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Notes</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#3f3a36]">
                  {paginatedGlossary.map(({ t, origIdx }) => (
                    <tr key={origIdx} className="hover:bg-[#2b2622]/40 transition-colors">
                      <td className="p-3 font-medium text-[#f7f5f0] font-mono">
                        {t.source || t.term}
                      </td>
                      <td className="p-3 text-emerald-400 font-medium font-mono">
                        {t.target || t.translation}
                      </td>
                      <td className="p-3">
                        <span className="px-1.5 py-0.2 rounded-[2px] bg-[#2b2622] text-[#aea69c] border border-[#3f3a36] text-[10px] font-mono uppercase">
                          {t.category || 'term'}
                        </span>
                      </td>
                      <td className="p-3 text-[#c9c0ad] max-w-xs truncate">
                        {t.notes || '—'}
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openEditTermModal(t, origIdx)}
                            className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer"
                            aria-label={`Edit term ${t.source || t.term}`}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteTerm(origIdx)}
                            className="p-1 text-[#aea69c] hover:text-rose-400 cursor-pointer"
                            aria-label={`Delete term ${t.source || t.term}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredGlossary.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-[#aea69c] font-mono">
                        {searchTerm || termCategoryFilter !== 'all'
                          ? 'No glossary terms found matching your filter.'
                          : 'No glossary terms registered in Novel Bible yet.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={safeGlossaryPage}
              totalPages={glossaryTotalPages}
              totalItems={filteredGlossary.length}
              pageSize={glossaryPageSize}
              pageSizeOptions={[25, 50, 100]}
              onPageChange={setGlossaryPage}
              onPageSizeChange={(newSize) => {
                setGlossaryPageSize(newSize);
                setGlossaryPage(1);
              }}
              itemName="terms"
            />
          </div>
        ) : activeTab === 'memory' ? (
          /* NARRATIVE MEMORY VIEW */
          <div className="space-y-6 max-w-4xl">
            {/* Macro Story Summary */}
            <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#dad2c1]" />
                  <h3 className="font-medium text-[#f7f5f0] text-sm">
                    Macro Narrative Context (Whole Story Summary)
                  </h3>
                </div>
                <button
                  onClick={() => bible && handleSaveBible(bible)}
                  disabled={saving}
                  className="btn-primary text-xs"
                >
                  Save Summary
                </button>
              </div>
              <textarea
                value={bible?.whole_story_summary || ''}
                onChange={(e) =>
                  bible && setBible({ ...bible, whole_story_summary: e.target.value })
                }
                rows={8}
                className="w-full bg-[#24201d] border border-[#3f3a36] rounded-[3px] p-3 text-xs text-[#dad2c1] leading-relaxed font-mono focus:outline-none focus:border-[#dad2c1]"
                placeholder="Overarching summary of the entire series maintained by the Chronicler Agent..."
              />
            </div>

            {/* Active Story Arc (Meso Ongoing) */}
            {bible?.active_arc && (
              <div className="bg-[#29231c] border border-amber-600/40 rounded-[4px] p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Bookmark className="w-4 h-4 text-amber-400" />
                    <h3 className="font-medium text-[#f7f5f0] text-sm flex items-center gap-2">
                      Active Story Arc (Ongoing)
                      <span className="text-[10px] px-2 py-0.5 bg-amber-500/20 text-amber-300 rounded border border-amber-500/30 uppercase tracking-wide font-medium">
                        ▶ Active
                      </span>
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveArcExpanded(!activeArcExpanded)}
                    className="text-xs text-[#aea69c] hover:text-[#f7f5f0] flex items-center gap-1 cursor-pointer transition-colors"
                  >
                    <span>{activeArcExpanded ? 'Collapse' : 'Expand'}</span>
                    {activeArcExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                <div
                  onClick={() => setActiveArcExpanded(!activeArcExpanded)}
                  className="p-3.5 bg-[#24201d] border border-amber-600/30 rounded-[3px] cursor-pointer hover:border-amber-500/50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-[#f7f5f0]">
                        Arc #{bible.active_arc.arc_num ?? bible.active_arc.arc_number ?? 1}:{' '}
                        {bible.active_arc.title || bible.active_arc.arc_title || 'Ongoing Arc'}
                      </span>
                      {bible.active_arc.arc_id && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 bg-[#2f2a26] text-[#aea69c] rounded border border-[#3f3a36]">
                          {bible.active_arc.arc_id}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {bible.active_arc.folder && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#2c2825] text-[#b3aa9d] rounded border border-[#443e39] font-mono">
                          Vol: {bible.active_arc.folder}
                        </span>
                      )}
                      <span className="text-[10px] px-1.5 py-0.5 bg-[#2c2825] text-[#dad2c1] rounded border border-[#443e39] font-mono">
                        From Ch. {bible.active_arc.start_chapter ?? 1}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedArcModal(bible.active_arc!);
                        }}
                        title="View full details"
                        className="p-1 text-[#8e8579] hover:text-[#f7f5f0] hover:bg-[#383330] rounded transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {!activeArcExpanded && (bible.active_arc.synopsis || bible.active_arc.summary) && (
                    <div className="text-xs text-[#c9c0ad] mt-1.5 line-clamp-1 leading-relaxed">
                      {bible.active_arc.synopsis || bible.active_arc.summary}
                    </div>
                  )}

                  {activeArcExpanded && (
                    <div className="mt-3 pt-3 border-t border-[#3f3a36] space-y-3">
                      {bible.active_arc.core_conflict && (
                        <div className="bg-[#241e18] border border-amber-900/40 rounded p-2.5">
                          <div className="text-[10px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                            <Target className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                            Core Conflict & Narrative Stakes
                          </div>
                          <p className="text-xs text-[#dad2c1] leading-relaxed">
                            {bible.active_arc.core_conflict}
                          </p>
                        </div>
                      )}
                      {(bible.active_arc.synopsis || bible.active_arc.summary) && (
                        <div className="space-y-1">
                          <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                            Narrative Progression
                          </div>
                          <p className="text-xs text-[#dad2c1] leading-relaxed whitespace-pre-wrap">
                            {bible.active_arc.synopsis || bible.active_arc.summary}
                          </p>
                        </div>
                      )}
                      {bible.active_arc.key_milestones && bible.active_arc.key_milestones.length > 0 && (
                        <div className="space-y-1">
                          <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                            Milestones Achieved So Far
                          </div>
                          <div className="space-y-1 pl-1">
                            {bible.active_arc.key_milestones.map((m, mIdx) => (
                              <div key={mIdx} className="text-xs text-[#dad2c1] flex items-start gap-2">
                                <CheckCircle2 className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                                <span>{m}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Meso Story Arcs */}
            <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#dad2c1]" />
                  <h3 className="font-medium text-[#f7f5f0] text-sm">
                    Archived Story Arcs ({bible?.archived_arcs?.length ?? 0})
                  </h3>
                </div>

                {bible?.archived_arcs && bible.archived_arcs.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-[#aea69c]" />
                      <input
                        type="text"
                        placeholder="Filter arcs..."
                        value={searchArc}
                        onChange={(e) => setSearchArc(e.target.value)}
                        className="bg-[#24201d] border border-[#3f3a36] rounded-[3px] pl-8 pr-6 py-1 text-xs text-[#dad2c1] placeholder-[#8e8579] focus:outline-none focus:border-[#dad2c1] w-36 sm:w-44"
                      />
                      {searchArc && (
                        <button
                          type="button"
                          onClick={() => setSearchArc('')}
                          className="absolute right-2 top-1.5 text-[#aea69c] hover:text-[#f7f5f0]"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => expandAllArcs(bible.archived_arcs?.length ?? 0)}
                      className="btn-secondary text-[11px] py-1 px-2 flex items-center gap-1"
                      title="Expand all arc details"
                    >
                      <ChevronDown className="w-3 h-3" />
                      <span>Expand All</span>
                    </button>
                    <button
                      type="button"
                      onClick={collapseAllArcs}
                      className="btn-secondary text-[11px] py-1 px-2 flex items-center gap-1"
                      title="Collapse all arc details"
                    >
                      <ChevronUp className="w-3 h-3" />
                      <span>Collapse All</span>
                    </button>
                  </div>
                )}
              </div>

              {bible?.archived_arcs && bible.archived_arcs.length > 0 ? (
                (() => {
                  const filteredArcs = bible.archived_arcs
                    .map((arc, origIdx) => ({ arc, origIdx }))
                    .filter(({ arc, origIdx }) => {
                      if (!searchArc.trim()) return true;
                      const q = searchArc.toLowerCase();
                      const title = (arc.title || arc.arc_title || '').toLowerCase();
                      const synopsis = (arc.synopsis || arc.summary || '').toLowerCase();
                      const conflict = (arc.core_conflict || '').toLowerCase();
                      const num = String(arc.arc_num ?? arc.arc_number ?? origIdx + 1);
                      const folder = (arc.folder || '').toLowerCase();
                      return (
                        title.includes(q) ||
                        synopsis.includes(q) ||
                        conflict.includes(q) ||
                        num.includes(q) ||
                        folder.includes(q)
                      );
                    });

                  if (filteredArcs.length === 0) {
                    return (
                      <div className="text-xs text-[#aea69c] italic p-4 text-center bg-[#24201d] rounded border border-[#3f3a36]">
                        No story arcs match filter "{searchArc}".
                      </div>
                    );
                  }

                  return (
                    <div className="space-y-3">
                      {filteredArcs.map(({ arc, origIdx }) => {
                        const arcNum = arc.arc_num ?? arc.arc_number ?? origIdx + 1;
                        const arcTitle = arc.title || arc.arc_title || 'Untitled Arc';
                        const arcSynopsis = arc.synopsis || arc.summary || '';
                        const isExpanded = expandedArcIndices.has(origIdx);

                        return (
                          <div
                            key={arc.arc_id || origIdx}
                            className="bg-[#24201d] border border-[#3f3a36] hover:border-[#524b45] rounded-[4px] transition-all overflow-hidden"
                          >
                            <div
                              onClick={() => toggleArcExpanded(origIdx)}
                              className="w-full text-left p-3.5 flex items-center justify-between gap-3 cursor-pointer select-none hover:bg-[#2b2622] transition-colors"
                            >
                              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                                <span className="text-[#aea69c] hover:text-[#f7f5f0] p-0.5 rounded transition-transform">
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-[#dad2c1] shrink-0" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-[#aea69c] shrink-0" />
                                  )}
                                </span>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-semibold text-xs text-[#f7f5f0]">
                                      Arc #{arcNum}: {arcTitle}
                                    </span>
                                    {arc.arc_id && (
                                      <span className="text-[10px] font-mono px-1.5 py-0.5 bg-[#2f2a26] text-[#aea69c] rounded border border-[#3f3a36]">
                                        {arc.arc_id}
                                      </span>
                                    )}
                                  </div>
                                  {!isExpanded && arcSynopsis && (
                                    <p className="text-[11px] text-[#9c9488] line-clamp-1 mt-0.5 leading-relaxed">
                                      {arcSynopsis}
                                    </p>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                {arc.folder && (
                                  <span className="text-[10px] px-1.5 py-0.5 bg-[#2c2825] text-[#b3aa9d] rounded border border-[#443e39] font-mono">
                                    Vol: {arc.folder}
                                  </span>
                                )}
                                <span className="text-[10px] px-1.5 py-0.5 bg-[#2c2825] text-[#dad2c1] rounded border border-[#443e39] font-mono">
                                  Ch. {arc.start_chapter ?? 1}{arc.end_chapter ? `–${arc.end_chapter}` : '+'}
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 bg-[#1a2c20] text-[#7ecb94] rounded border border-[#2d5038] uppercase tracking-wide font-medium">
                                  {arc.status || 'Completed'}
                                </span>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedArcModal(arc);
                                  }}
                                  title="View full details"
                                  className="p-1 text-[#8e8579] hover:text-[#f7f5f0] hover:bg-[#383330] rounded transition-colors"
                                >
                                  <Eye className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>

                            {isExpanded && (
                              <div className="border-t border-[#332e2b] p-4 bg-[#1e1a18] space-y-3.5">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                  <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                                    <div className="text-[10px] text-[#8e8579] uppercase font-mono">Arc Identifier</div>
                                    <div className="font-mono text-[#dad2c1] font-medium mt-0.5">
                                      {arc.arc_id || `arc_${String(arcNum).padStart(4, '0')}`}
                                    </div>
                                  </div>
                                  <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                                    <div className="text-[10px] text-[#8e8579] uppercase font-mono">Chapters</div>
                                    <div className="font-mono text-[#dad2c1] font-medium mt-0.5">
                                      Ch. {arc.start_chapter ?? 1} – {arc.end_chapter ?? 'Ongoing'}
                                    </div>
                                  </div>
                                  <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                                    <div className="text-[10px] text-[#8e8579] uppercase font-mono">Volume Scope</div>
                                    <div className="text-[#dad2c1] font-medium mt-0.5 truncate">
                                      {arc.folder || 'Global'}
                                    </div>
                                  </div>
                                  <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                                    <div className="text-[10px] text-[#8e8579] uppercase font-mono">Lifecycle State</div>
                                    <div className="text-[#7ecb94] font-medium mt-0.5 capitalize">
                                      {arc.status || 'Completed'}
                                    </div>
                                  </div>
                                </div>

                                {arc.core_conflict && (
                                  <div className="bg-[#26201b] border border-amber-900/30 rounded p-3">
                                    <div className="text-[10px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                                      <Target className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                                      Core Conflict & Narrative Stakes
                                    </div>
                                    <p className="text-xs text-[#dad2c1] leading-relaxed">
                                      {arc.core_conflict}
                                    </p>
                                  </div>
                                )}

                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                                    Arc Progression & Synopsis
                                  </div>
                                  <p className="text-xs text-[#c9c0ad] leading-relaxed whitespace-pre-wrap bg-[#24201d] border border-[#383330] rounded p-3">
                                    {arcSynopsis || 'No narrative synopsis recorded for this arc.'}
                                  </p>
                                </div>

                                {arc.key_milestones && arc.key_milestones.length > 0 && (
                                  <div className="space-y-1.5">
                                    <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                                      Key Milestones Achieved ({arc.key_milestones.length})
                                    </div>
                                    <div className="bg-[#24201d] border border-[#383330] rounded p-3 space-y-1.5">
                                      {arc.key_milestones.map((milestone, mIdx) => (
                                        <div key={mIdx} className="text-xs text-[#dad2c1] flex items-start gap-2">
                                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                                          <span className="leading-relaxed">{milestone}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()
              ) : (
                <div className="text-xs text-[#aea69c] italic">
                  No completed story arcs archived yet. ChroniclerAgent archives story arcs automatically upon resolution.
                </div>
              )}
            </div>
          </div>
        ) : (
          /* RAW YAML VIEW */
          <div className="h-full flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-[#aea69c]">
                Directly edit <code className="text-[#dad2c1] font-mono">.novel/bible/bible.yaml</code>.
              </span>
              <button
                onClick={handleSaveRawYaml}
                disabled={saving}
                className="btn-primary text-xs flex items-center gap-1.5"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{saving ? 'Saving...' : 'Save YAML'}</span>
              </button>
            </div>

            <textarea
              value={rawYaml}
              onChange={(e) => setRawYaml(e.target.value)}
              disabled={loadingRaw}
              className="flex-1 w-full bg-[#24201d] border border-[#3f3a36] rounded-[4px] p-4 font-mono text-xs text-[#dad2c1] leading-normal focus:outline-none focus:border-[#dad2c1]"
              placeholder="Loading raw bible.yaml..."
            />
          </div>
        )}
      </div>

      {/* Character Edit/Add Modal */}
      {isCharModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-[#f7f5f0]">
                {editingCharIndex !== null ? 'Edit Character' : 'Add Character'}
              </h2>
              <button
                onClick={() => setIsCharModalOpen(false)}
                className="text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Structured Name Breakdown Section */}
            <div className="bg-[#24201d] border border-[#3f3a36] rounded-[4px] p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-[#dad2c1] uppercase tracking-wider font-mono">
                  Name Breakdown (Source & Target)
                </span>
                <button
                  type="button"
                  onClick={() => {
                    const srcFull = assembleFullName(charForm.names?.source, true);
                    const tgtFull = assembleFullName(charForm.names?.target, false);
                    setCharForm({
                      ...charForm,
                      original_name: srcFull || charForm.original_name,
                      name: tgtFull || charForm.name,
                    });
                  }}
                  className="text-[10px] font-mono text-[#dad2c1] hover:text-[#f7f5f0] bg-[#383330] hover:bg-[#453f3a] border border-[#3f3a36] px-2 py-0.5 rounded-[2px] cursor-pointer transition-colors"
                >
                  ⚡ Auto-Assemble Full Names
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {/* Source Language Column */}
                <div className="space-y-1.5 p-2 bg-[#1e1b18] rounded border border-[#383330]">
                  <div className="text-[10px] font-mono text-emerald-400 font-medium">
                    {bible?.source_language || 'Source'} Script
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Given / First (name)</label>
                    <input
                      type="text"
                      value={charForm.names?.source?.name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: { ...charForm.names?.source, name: e.target.value },
                            target: charForm.names?.target || {},
                          },
                        })
                      }
                      className="input-text w-full text-xs font-mono py-1"
                      placeholder="e.g. メアリィ"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Middle / Particle (m_name)</label>
                    <input
                      type="text"
                      value={charForm.names?.source?.m_name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: { ...charForm.names?.source, m_name: e.target.value },
                            target: charForm.names?.target || {},
                          },
                        })
                      }
                      className="input-text w-full text-xs font-mono py-1"
                      placeholder="e.g. ルクア"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Surname / Family (s_name)</label>
                    <input
                      type="text"
                      value={charForm.names?.source?.s_name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: { ...charForm.names?.source, s_name: e.target.value },
                            target: charForm.names?.target || {},
                          },
                        })
                      }
                      className="input-text w-full text-xs font-mono py-1"
                      placeholder="e.g. レガリヤ"
                    />
                  </div>
                </div>

                {/* Target Language Column */}
                <div className="space-y-1.5 p-2 bg-[#1e1b18] rounded border border-[#383330]">
                  <div className="text-[10px] font-mono text-amber-300 font-medium">
                    {bible?.target_language || 'Target'} Translation
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Given / First (name)</label>
                    <input
                      type="text"
                      value={charForm.names?.target?.name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: charForm.names?.source || {},
                            target: { ...charForm.names?.target, name: e.target.value },
                          },
                        })
                      }
                      className="input-text w-full text-xs py-1"
                      placeholder="e.g. Mary"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Middle / Particle (m_name)</label>
                    <input
                      type="text"
                      value={charForm.names?.target?.m_name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: charForm.names?.source || {},
                            target: { ...charForm.names?.target, m_name: e.target.value },
                          },
                        })
                      }
                      className="input-text w-full text-xs py-1"
                      placeholder="e.g. Lukia"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#aea69c]">Surname / Family (s_name)</label>
                    <input
                      type="text"
                      value={charForm.names?.target?.s_name || ''}
                      onChange={(e) =>
                        setCharForm({
                          ...charForm,
                          names: {
                            ...charForm.names,
                            source: charForm.names?.source || {},
                            target: { ...charForm.names?.target, s_name: e.target.value },
                          },
                        })
                      }
                      className="input-text w-full text-xs py-1"
                      placeholder="e.g. Legalia"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[#aea69c] mb-1">
                  {bible?.target_language ? `${bible.target_language} Full Name *` : 'Target Full Name *'}
                </label>
                <input
                  type="text"
                  value={charForm.name}
                  onChange={(e) => setCharForm({ ...charForm, name: e.target.value })}
                  className="input-text w-full"
                  placeholder="e.g. Eleanor"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">
                  {bible?.source_language ? `${bible.source_language} Original Full Name *` : 'Source Original Full Name *'}
                </label>
                <input
                  type="text"
                  value={charForm.original_name}
                  onChange={(e) =>
                    setCharForm({ ...charForm, original_name: e.target.value })
                  }
                  className="input-text w-full font-mono"
                  placeholder="e.g. エレノア"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Gender</label>
                <input
                  type="text"
                  value={charForm.gender || ''}
                  onChange={(e) => setCharForm({ ...charForm, gender: e.target.value })}
                  className="input-text w-full"
                  placeholder="female, male, unknown"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Role</label>
                <input
                  type="text"
                  value={charForm.role || ''}
                  onChange={(e) => setCharForm({ ...charForm, role: e.target.value })}
                  className="input-text w-full"
                  placeholder="Protagonist, Rival, Villainess"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[#aea69c] mb-1">Aliases & Nicknames (comma-separated)</label>
                <input
                  type="text"
                  value={aliasesInput}
                  onChange={(e) => setAliasesInput(e.target.value)}
                  className="input-text w-full"
                  placeholder="e.g. Black Beast, Sword Sovereign, Saintess"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Power Level / Realm</label>
                <input
                  type="text"
                  value={charForm.power_level || ''}
                  onChange={(e) => setCharForm({ ...charForm, power_level: e.target.value })}
                  className="input-text w-full"
                  placeholder="e.g. Level 99, Core Formation"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Status</label>
                <input
                  type="text"
                  value={charForm.status || ''}
                  onChange={(e) => setCharForm({ ...charForm, status: e.target.value })}
                  className="input-text w-full"
                  placeholder="e.g. Active, Injured, Deceased"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[#aea69c] mb-1">
                  Relationships (Target: relation, comma-separated)
                </label>
                <input
                  type="text"
                  value={relationshipsInput}
                  onChange={(e) => setRelationshipsInput(e.target.value)}
                  className="input-text w-full"
                  placeholder="e.g. Elena: sister, Gabriel: rival, Demon King: enemy"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[#aea69c] mb-1">Speaking Style / Voice</label>
                <input
                  type="text"
                  value={charForm.speaking_style || charForm.voice || ''}
                  onChange={(e) =>
                    setCharForm({
                      ...charForm,
                      speaking_style: e.target.value,
                      voice: e.target.value,
                    })
                  }
                  className="input-text w-full"
                  placeholder="e.g. haughty noblewoman, playful catgirl, calm elder"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-[#aea69c] mb-1">Summary & Lore</label>
                <textarea
                  value={charForm.summary || ''}
                  onChange={(e) => setCharForm({ ...charForm, summary: e.target.value })}
                  rows={3}
                  className="input-text w-full leading-relaxed"
                  placeholder="Key background information, personality traits, and secrets..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsCharModalOpen(false)}
                className="btn-secondary text-xs"
              >
                Cancel
              </button>
              <button
                onClick={saveCharModal}
                className="btn-primary text-xs"
              >
                Save Character
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Term Edit/Add Modal */}
      {isTermModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-[#f7f5f0]">
                {editingTermIndex !== null ? 'Edit Glossary Term' : 'Add Glossary Term'}
              </h2>
              <button
                onClick={() => setIsTermModalOpen(false)}
                className="text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-[#aea69c] mb-1">Source Term *</label>
                <input
                  type="text"
                  value={termForm.term || termForm.source || ''}
                  onChange={(e) =>
                    setTermForm({
                      ...termForm,
                      term: e.target.value,
                      source: e.target.value,
                    })
                  }
                  className="input-text w-full font-mono"
                  placeholder="e.g. 聖剣"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Standard Translation *</label>
                <input
                  type="text"
                  value={termForm.translation || termForm.target || ''}
                  onChange={(e) =>
                    setTermForm({
                      ...termForm,
                      translation: e.target.value,
                      target: e.target.value,
                    })
                  }
                  className="input-text w-full font-medium"
                  placeholder="e.g. Holy Sword"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Category</label>
                <input
                  type="text"
                  value={termForm.category || ''}
                  onChange={(e) => setTermForm({ ...termForm, category: e.target.value })}
                  className="input-text w-full"
                  placeholder="weapon, place, title, skill, artifact"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Notes</label>
                <input
                  type="text"
                  value={termForm.notes || ''}
                  onChange={(e) => setTermForm({ ...termForm, notes: e.target.value })}
                  className="input-text w-full"
                  placeholder="Usage context or nuances..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsTermModalOpen(false)}
                className="btn-secondary text-xs"
              >
                Cancel
              </button>
              <button
                onClick={saveTermModal}
                className="btn-primary text-xs"
              >
                Save Term
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Story Arc Detail Modal */}
      {selectedArcModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-2xl w-full p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-[#3f3a36]">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-[#f7f5f0]">
                  Arc #{selectedArcModal.arc_num ?? selectedArcModal.arc_number ?? '?'}:{' '}
                  {selectedArcModal.title || selectedArcModal.arc_title || 'Untitled Arc'}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setSelectedArcModal(null)}
                className="text-[#aea69c] hover:text-[#f7f5f0] p-1 rounded hover:bg-[#383330] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                <div className="text-[10px] text-[#8e8579] uppercase font-mono">Arc Identifier</div>
                <div className="font-mono text-[#dad2c1] font-medium mt-0.5">
                  {selectedArcModal.arc_id || 'N/A'}
                </div>
              </div>
              <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                <div className="text-[10px] text-[#8e8579] uppercase font-mono">Chapters</div>
                <div className="font-mono text-[#dad2c1] font-medium mt-0.5">
                  Ch. {selectedArcModal.start_chapter ?? 1} – {selectedArcModal.end_chapter ?? 'Ongoing'}
                </div>
              </div>
              <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                <div className="text-[10px] text-[#8e8579] uppercase font-mono">Volume Scope</div>
                <div className="text-[#dad2c1] font-medium mt-0.5 truncate">
                  {selectedArcModal.folder || 'Global'}
                </div>
              </div>
              <div className="bg-[#24201d] border border-[#383330] rounded p-2">
                <div className="text-[10px] text-[#8e8579] uppercase font-mono">Status</div>
                <div className="text-[#7ecb94] font-medium mt-0.5 capitalize">
                  {selectedArcModal.status || 'Completed'}
                </div>
              </div>
            </div>

            {selectedArcModal.core_conflict && (
              <div className="bg-[#26201b] border border-amber-900/30 rounded p-3">
                <div className="text-[10px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Target className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  Core Conflict & Narrative Goal
                </div>
                <p className="text-xs text-[#dad2c1] leading-relaxed">
                  {selectedArcModal.core_conflict}
                </p>
              </div>
            )}

            <div className="space-y-1">
              <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                Narrative Progression & Synopsis
              </div>
              <p className="text-xs text-[#c9c0ad] leading-relaxed whitespace-pre-wrap bg-[#24201d] border border-[#383330] rounded p-3 max-h-60 overflow-y-auto">
                {selectedArcModal.synopsis || selectedArcModal.summary || 'No narrative synopsis recorded.'}
              </p>
            </div>

            {selectedArcModal.key_milestones && selectedArcModal.key_milestones.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold text-[#aea69c] uppercase tracking-wider">
                  Key Milestones Achieved ({selectedArcModal.key_milestones.length})
                </div>
                <div className="bg-[#24201d] border border-[#383330] rounded p-3 space-y-1.5 max-h-48 overflow-y-auto">
                  {selectedArcModal.key_milestones.map((milestone, mIdx) => (
                    <div key={mIdx} className="text-xs text-[#dad2c1] flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                      <span className="leading-relaxed">{milestone}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-[#3f3a36]">
              <button
                type="button"
                onClick={() => setSelectedArcModal(null)}
                className="btn-secondary text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
