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
  Eye
} from 'lucide-react';
import { BibleData, BibleCharacter, BibleTerm } from '../types/dashboard';
import {
  fetchBible,
  updateBible,
  fetchRawBible,
  updateRawBible
} from '../services/dashboardApi';
import { CharacterVisualizer } from './CharacterVisualizer';

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

  // Character Modal / Form
  const [isCharModalOpen, setIsCharModalOpen] = useState(false);
  const [editingCharIndex, setEditingCharIndex] = useState<number | null>(null);
  const [aliasesInput, setAliasesInput] = useState('');
  const [relationshipsInput, setRelationshipsInput] = useState('');
  const [charForm, setCharForm] = useState<BibleCharacter>({
    name: '',
    original_name: '',
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
  }, [activeProjectPath]);

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

  // Character Operations
  const openAddCharModal = () => {
    setEditingCharIndex(null);
    setCharForm({
      name: '',
      original_name: '',
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
    setCharForm({
      ...char,
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

  // Filtered lists
  const filteredChars = (bible?.characters || []).filter((c) => {
    const q = searchChar.toLowerCase();
    return (
      c.name.toLowerCase().includes(q) ||
      c.original_name.toLowerCase().includes(q) ||
      (c.role && c.role.toLowerCase().includes(q))
    );
  });

  const categories = Array.from(
    new Set((bible?.glossary || []).map((t) => t.category).filter(Boolean))
  ) as string[];

  const filteredGlossary = (bible?.glossary || []).filter((t) => {
    const q = searchTerm.toLowerCase();
    const termVal = (t.source || t.term || '').toLowerCase();
    const transVal = (t.target || t.translation || '').toLowerCase();
    const matchesSearch = termVal.includes(q) || transVal.includes(q);
    const matchesCat =
      termCategoryFilter === 'all' ? true : t.category === termCategoryFilter;
    return matchesSearch && matchesCat;
  });

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
        <div className="flex items-center gap-0.5 bg-[#2b2622] p-0.5 rounded-[4px] border border-[#3f3a36]">
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

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredChars.map((c, i) => (
                <div
                  key={i}
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
                            const origIdx = (bible?.characters || []).indexOf(c);
                            setSelectedCharIndex(origIdx !== -1 ? origIdx : i);
                            setActiveTab('visualizer');
                          }}
                          title="Visualize Character Sheet & Network"
                          aria-label={`Visualize ${c.name}`}
                          className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => openEditCharModal(c, i)}
                          title="Edit"
                          aria-label={`Edit ${c.name}`}
                          className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer transition-colors"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => deleteChar(i)}
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
                  {filteredGlossary.map((t, i) => (
                    <tr key={i} className="hover:bg-[#2b2622]/40 transition-colors">
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
                            onClick={() => openEditTermModal(t, i)}
                            className="p-1 text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer"
                            aria-label={`Edit term ${t.source || t.term}`}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteTerm(i)}
                            className="p-1 text-[#aea69c] hover:text-rose-400 cursor-pointer"
                            aria-label={`Delete term ${t.source || t.term}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

            {/* Meso Story Arcs */}
            <div className="bg-[#383330] border border-[#3f3a36] rounded-[4px] p-5">
              <h3 className="font-medium text-[#f7f5f0] text-sm mb-3">
                Archived Story Arcs ({bible?.archived_arcs?.length ?? 0})
              </h3>
              {bible?.archived_arcs && bible.archived_arcs.length > 0 ? (
                <div className="space-y-3">
                  {bible.archived_arcs.map((arc, i) => (
                    <div key={i} className="p-3 bg-[#24201d] border border-[#3f3a36] rounded-[3px]">
                      <div className="font-medium text-xs text-[#f7f5f0]">
                        Arc #{arc.arc_number ?? i + 1}: {arc.arc_title || 'Untitled Arc'}
                      </div>
                      <div className="text-xs text-[#c9c0ad] mt-1 leading-relaxed">
                        {arc.summary}
                      </div>
                    </div>
                  ))}
                </div>
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
          <div className="bg-[#2b2622] border border-[#3f3a36] rounded-[6px] max-w-lg w-full p-6 space-y-4 shadow-2xl">
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

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[#aea69c] mb-1">English Name *</label>
                <input
                  type="text"
                  value={charForm.name}
                  onChange={(e) => setCharForm({ ...charForm, name: e.target.value })}
                  className="input-text w-full"
                  placeholder="e.g. Eleanor"
                />
              </div>
              <div>
                <label className="block text-[#aea69c] mb-1">Original Name *</label>
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
    </div>
  );
};
