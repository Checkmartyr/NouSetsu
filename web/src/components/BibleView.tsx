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
  BookOpen
} from 'lucide-react';
import { BibleData, BibleCharacter, BibleTerm } from '../types/dashboard';
import {
  fetchBible,
  updateBible,
  fetchRawBible,
  updateRawBible
} from '../services/dashboardApi';

interface BibleViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
}

type BibleTab = 'characters' | 'glossary' | 'memory' | 'raw';

export const BibleView: React.FC<BibleViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
}) => {
  const [activeTab, setActiveTab] = useState<BibleTab>('characters');
  const [bible, setBible] = useState<BibleData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

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
      role: '',
      speaking_style: '',
      power_level: '',
      status: '',
      summary: '',
    });
    setIsCharModalOpen(true);
  };

  const openEditCharModal = (char: BibleCharacter, index: number) => {
    setEditingCharIndex(index);
    setCharForm({
      ...char,
      speaking_style: char.speaking_style || char.voice || '',
      voice: char.voice || char.speaking_style || '',
    });
    setIsCharModalOpen(true);
  };

  const saveCharModal = () => {
    if (!bible) return;
    const finalCharForm: BibleCharacter = {
      ...charForm,
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
    <div className="flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-20 right-8 z-50 px-4 py-2 bg-emerald-600 text-white rounded-lg shadow-xl text-sm font-medium flex items-center gap-2">
          <Check className="w-4 h-4" />
          {toast}
        </div>
      )}

      {/* Header & Subnav */}
      <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BookMarked className="w-5 h-5 text-indigo-400" />
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Novel Bible: {bible?.title || activeProjectTitle || 'Series Memory'}
            </h1>
            {bible?.genre && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                {bible.genre}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Canonical terminology, character profiles, voice registers & narrative lore.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('characters')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              activeTab === 'characters'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            Characters ({bible?.characters?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab('glossary')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              activeTab === 'glossary'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            Glossary ({bible?.glossary?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab('memory')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              activeTab === 'memory'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Narrative Memory
          </button>
          <button
            onClick={() => setActiveTab('raw')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
              activeTab === 'raw'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            Raw YAML
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-center py-20 text-slate-500">Loading Bible data...</div>
        ) : activeTab === 'characters' ? (
          /* CHARACTERS VIEW */
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search characters by name or role..."
                  value={searchChar}
                  onChange={(e) => setSearchChar(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <button
                onClick={openAddCharModal}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow cursor-pointer transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Character
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredChars.map((c, i) => (
                <div
                  key={i}
                  className="bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-xl p-4 flex flex-col justify-between transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h2 className="text-base font-bold text-slate-100">{c.name}</h2>
                        <span className="text-xs text-indigo-400 font-mono">
                          {c.original_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openEditCharModal(c, i)}
                          title="Edit"
                          aria-label={`Edit ${c.name}`}
                          className="p-1 text-slate-400 hover:text-indigo-400 cursor-pointer"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => deleteChar(i)}
                          title="Delete"
                          aria-label={`Delete ${c.name}`}
                          className="p-1 text-slate-400 hover:text-rose-400 cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {c.gender && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {c.gender}
                        </span>
                      )}
                      {c.role && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                          {c.role}
                        </span>
                      )}
                      {c.power_level && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                          {c.power_level}
                        </span>
                      )}
                    </div>

                    {(c.speaking_style || c.voice) && (
                      <p className="text-xs text-slate-400 mt-2 italic">
                        &ldquo;{c.speaking_style || c.voice}&rdquo;
                      </p>
                    )}

                    {c.summary && (
                      <p className="text-xs text-slate-300 mt-2 line-clamp-3">
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
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search terms or translations..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <select
                  value={termCategoryFilter}
                  onChange={(e) => setTermCategoryFilter(e.target.value)}
                  aria-label="Filter glossary by category"
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
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
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow cursor-pointer transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Term
              </button>
            </div>

            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/40">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="p-3">Source Term</th>
                    <th className="p-3">Standard Translation</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Notes</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredGlossary.map((t, i) => (
                    <tr key={i} className="hover:bg-slate-900/60 transition-colors">
                      <td className="p-3 font-medium text-slate-200 font-mono">
                        {t.source || t.term}
                      </td>
                      <td className="p-3 text-emerald-400 font-semibold">
                        {t.target || t.translation}
                      </td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] uppercase">
                          {t.category || 'term'}
                        </span>
                      </td>
                      <td className="p-3 text-slate-400 max-w-xs truncate">
                        {t.notes || '—'}
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => openEditTermModal(t, i)}
                            className="p-1 text-slate-400 hover:text-indigo-400 cursor-pointer"
                            aria-label={`Edit term ${t.source || t.term}`}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteTerm(i)}
                            className="p-1 text-slate-400 hover:text-rose-400 cursor-pointer"
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
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <h3 className="font-semibold text-slate-200 text-sm">
                    Macro Narrative Context (Whole Story Summary)
                  </h3>
                </div>
                <button
                  onClick={() => bible && handleSaveBible(bible)}
                  disabled={saving}
                  className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium cursor-pointer"
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
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 leading-relaxed font-mono focus:outline-none focus:border-indigo-500"
                placeholder="Overarching summary of the entire series maintained by the Chronicler Agent..."
              />
            </div>

            {/* Meso Story Arcs */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <h3 className="font-semibold text-slate-200 text-sm mb-3">
                Archived Story Arcs ({bible?.archived_arcs?.length ?? 0})
              </h3>
              {bible?.archived_arcs && bible.archived_arcs.length > 0 ? (
                <div className="space-y-3">
                  {bible.archived_arcs.map((arc, i) => (
                    <div key={i} className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                      <div className="font-semibold text-xs text-indigo-300">
                        Arc #{arc.arc_number ?? i + 1}: {arc.arc_title || 'Untitled Arc'}
                      </div>
                      <div className="text-xs text-slate-400 mt-1 leading-relaxed">
                        {arc.summary}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-500 italic">
                  No completed story arcs archived yet. ChroniclerAgent archives story arcs automatically upon resolution.
                </div>
              )}
            </div>
          </div>
        ) : (
          /* RAW YAML VIEW */
          <div className="h-full flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">
                Directly edit <code className="text-indigo-300">.novel/bible/bible.yaml</code>.
              </span>
              <button
                onClick={handleSaveRawYaml}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow"
              >
                <Save className="w-3.5 h-3.5" />
                {saving ? 'Saving...' : 'Save YAML'}
              </button>
            </div>

            <textarea
              value={rawYaml}
              onChange={(e) => setRawYaml(e.target.value)}
              disabled={loadingRaw}
              className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-200 leading-normal focus:outline-none focus:border-indigo-500 selection:bg-indigo-500/30"
              placeholder="Loading raw bible.yaml..."
            />
          </div>
        )}
      </div>

      {/* Character Edit/Add Modal */}
      {isCharModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-100">
                {editingCharIndex !== null ? 'Edit Character' : 'Add Character'}
              </h2>
              <button
                onClick={() => setIsCharModalOpen(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">English Name *</label>
                <input
                  type="text"
                  value={charForm.name}
                  onChange={(e) => setCharForm({ ...charForm, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="e.g. Eleanor"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Original Name *</label>
                <input
                  type="text"
                  value={charForm.original_name}
                  onChange={(e) =>
                    setCharForm({ ...charForm, original_name: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="e.g. エレノア"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Gender</label>
                <input
                  type="text"
                  value={charForm.gender || ''}
                  onChange={(e) => setCharForm({ ...charForm, gender: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="female, male, unknown"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Role</label>
                <input
                  type="text"
                  value={charForm.role || ''}
                  onChange={(e) => setCharForm({ ...charForm, role: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="Protagonist, Rival, Villainess"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-slate-400 mb-1">Speaking Style / Voice</label>
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="e.g. haughty noblewoman, playful catgirl, calm elder"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-slate-400 mb-1">Summary & Lore</label>
                <textarea
                  value={charForm.summary || ''}
                  onChange={(e) => setCharForm({ ...charForm, summary: e.target.value })}
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="Key background information, personality traits, and secrets..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsCharModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={saveCharModal}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Term Edit/Add Modal */}
      {isTermModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-100">
                {editingTermIndex !== null ? 'Edit Glossary Term' : 'Add Glossary Term'}
              </h2>
              <button
                onClick={() => setIsTermModalOpen(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Source Term *</label>
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  placeholder="e.g. 聖剣"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Standard Translation *</label>
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="e.g. Holy Sword"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Category</label>
                <input
                  type="text"
                  value={termForm.category || ''}
                  onChange={(e) => setTermForm({ ...termForm, category: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="weapon, place, title, skill, artifact"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Notes</label>
                <input
                  type="text"
                  value={termForm.notes || ''}
                  onChange={(e) => setTermForm({ ...termForm, notes: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
                  placeholder="Usage context or nuances..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsTermModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={saveTermModal}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
