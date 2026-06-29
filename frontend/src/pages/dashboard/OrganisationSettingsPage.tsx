import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { Plus, Trash2, Edit } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useNavigate } from 'react-router-dom';

export const OrganisationSettingsPage: React.FC = () => {
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  // Models CRUD state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  
  const [displayName, setDisplayName] = useState('');
  const [provider, setProvider] = useState<'anthropic' | 'openrouter'>('anthropic');
  const [modelString, setModelString] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [inputPrice, setInputPrice] = useState('');
  const [outputPrice, setOutputPrice] = useState('');

  const resetForm = () => {
    setDisplayName('');
    setProvider('anthropic');
    setModelString('');
    setIsActive(true);
    setInputPrice('');
    setOutputPrice('');
    setEditingModelId(null);
  };

  const { data: modelsData, refetch: refetchModels } = useQuery({
    queryKey: ['admin-models'],
    queryFn: adminService.getModels,
  });

  const createModelMutation = useMutation({
    mutationFn: adminService.createModel,
    onSuccess: () => {
      refetchModels();
      setIsAddModalOpen(false);
      resetForm();
    }
  });

  const updateModelMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminService.updateModel(id, data),
    onSuccess: () => {
      refetchModels();
      setIsAddModalOpen(false);
      resetForm();
    }
  });

  const deleteModelMutation = useMutation({
    mutationFn: adminService.deleteModel,
    onSuccess: () => {
      refetchModels();
    }
  });

  const handleSubmitModel = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      display_name: displayName,
      provider,
      model_string: modelString,
      is_active: isActive,
      input_price_per_million: inputPrice === '' ? null : parseFloat(inputPrice),
      output_price_per_million: outputPrice === '' ? null : parseFloat(outputPrice)
    };

    if (isEditing && editingModelId) {
      updateModelMutation.mutate({ id: editingModelId, data: payload });
    } else {
      createModelMutation.mutate(payload);
    }
  };

  const handleToggleActive = (model: any) => {
    updateModelMutation.mutate({
      id: model.id,
      data: { is_active: !model.is_active }
    });
  };

  const handleDeleteModel = (id: string) => {
    if (confirm('Are you sure you want to delete this model configuration?')) {
      deleteModelMutation.mutate(id);
    }
  };

  const [orgName, setOrgName] = useState('');
  const [orgWebsite, setOrgWebsite] = useState('');
  const [budgetLimit, setBudgetLimit] = useState('');
  const [defaultModelId, setDefaultModelId] = useState('');

  const { data: orgData } = useQuery({
    queryKey: ['organisation'],
    queryFn: adminService.getOrganisation,
  });

  useEffect(() => {
    if (orgData) {
      setOrgName(orgData.name);
      setOrgWebsite(orgData.website || '');
      setBudgetLimit(orgData.monthly_budget_limit != null ? orgData.monthly_budget_limit.toString() : '');
      setDefaultModelId(orgData.default_model_id || '');
    }
  }, [orgData]);

  const [generalUpdateStatus, setGeneralUpdateStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);
  const [budgetUpdateStatus, setBudgetUpdateStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  const updateGeneralMutation = useMutation({
    mutationFn: adminService.updateOrganisation,
    onSuccess: (data) => {
      setGeneralUpdateStatus({ type: 'success', msg: 'Organisation updated successfully' });
      setOrgName(data.name);
      setOrgWebsite(data.website || '');
      setDefaultModelId(data.default_model_id || '');
      setTimeout(() => setGeneralUpdateStatus(null), 3000);
    },
    onError: (err: any) => {
      setGeneralUpdateStatus({ type: 'error', msg: err.response?.data?.detail || 'Update failed' });
    }
  });

  const updateBudgetMutation = useMutation({
    mutationFn: adminService.updateOrganisation,
    onSuccess: (data) => {
      setBudgetUpdateStatus({ type: 'success', msg: 'Budget updated successfully' });
      setBudgetLimit(data.monthly_budget_limit != null ? data.monthly_budget_limit.toString() : '');
      setTimeout(() => setBudgetUpdateStatus(null), 3000);
    },
    onError: (err: any) => {
      setBudgetUpdateStatus({ type: 'error', msg: err.response?.data?.detail || 'Update failed' });
    }
  });

  const handleUpdateGeneral = (e: React.FormEvent) => {
    e.preventDefault();
    updateGeneralMutation.mutate({ 
      name: orgName, 
      website: orgWebsite,
      default_model_id: defaultModelId === '' ? null : defaultModelId
    });
  };

  const handleUpdateBudget = (e: React.FormEvent) => {
    e.preventDefault();
    updateBudgetMutation.mutate({ 
      monthly_budget_limit: budgetLimit === '' ? null : parseFloat(budgetLimit)
    });
  };

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmName, setDeleteConfirmName] = useState('');

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteOrganisation,
    onSuccess: async () => {
      logout();
      navigate('/login');
    }
  });

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  return (
    <div className="flex flex-col gap-6 w-full h-full pb-12 text-slate-800 dark:text-slate-100">
      <div className="shrink-0">
        <h1 className="text-2xl font-semibold font-sora text-slate-800 dark:text-slate-100">Organisation Settings</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Manage your organisation's settings, including general information, monthly budget, and available LLM models for RAG chat generation.
          </p>
      </div>

      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* General Card */}
          <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-4 font-sora">General</h2>
              <form onSubmit={handleUpdateGeneral} className="flex flex-col gap-4">
                {generalUpdateStatus && (
                  <div className={`p-3 rounded-lg text-sm border ${
                    generalUpdateStatus.type === 'success' 
                      ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50' 
                      : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50'
                  }`}>
                    {generalUpdateStatus.msg}
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Organisation Name</label>
                  <input required value={orgName} onChange={e=>setOrgName(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Website</label>
                  <input type="url" value={orgWebsite} onChange={e=>setOrgWebsite(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Default Chat Model</label>
                  <select
                    value={defaultModelId}
                    onChange={(e) => setDefaultModelId(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all cursor-pointer"
                  >
                    <option value="">System Default (Oldest Active Anthropic Model)</option>
                    {modelsData?.filter(m => m.is_active).map(m => (
                      <option key={m.id} value={m.id}>{m.display_name} ({m.model_string})</option>
                    ))}
                  </select>
                </div>
                <button type="submit" disabled={updateGeneralMutation.isPending} className="mt-2 w-fit px-6 bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50">
                  {updateGeneralMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </form>
            </div>
          </section>

          {/* Monthly Budget Card */}
          <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-4 font-sora">Monthly Budget</h2>
              <form onSubmit={handleUpdateBudget} className="flex flex-col gap-4">
                {budgetUpdateStatus && (
                  <div className={`p-3 rounded-lg text-sm border ${
                    budgetUpdateStatus.type === 'success' 
                      ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50' 
                      : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50'
                  }`}>
                    {budgetUpdateStatus.msg}
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Monthly Budget Limit ($ USD)</label>
                  <input type="number" step="0.01" min="0" placeholder="e.g. 100.00 (Leave blank for no limit)" value={budgetLimit} onChange={e=>setBudgetLimit(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
                </div>
                <button type="submit" disabled={updateBudgetMutation.isPending} className="mt-2 w-fit px-6 bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50">
                  {updateBudgetMutation.isPending ? 'Saving...' : 'Update Budget'}
                </button>
              </form>
            </div>
          </section>
        </div>

        <hr className="border-slate-200 dark:border-slate-800 my-2" />

        <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100 font-sora">Models Configuration</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Manage the available LLMs for RAG chat generation and system settings.</p>
            </div>
            <button
              onClick={() => {
                setIsEditing(false);
                setIsAddModalOpen(true);
                resetForm();
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg text-sm font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Model
            </button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800 text-left border-collapse">
              <thead className="bg-slate-50 dark:bg-slate-800/40">
                <tr>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Display Name</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Provider</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Model Identifier</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Price (In/Out per M)</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Status</th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900 text-sm">
                {!modelsData || modelsData.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-400 dark:text-slate-500">
                      No models configured. Add a model to get started.
                    </td>
                  </tr>
                ) : (
                  modelsData.map((model) => (
                    <tr key={model.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20">
                      <td className="px-4 py-3.5 font-medium text-slate-800 dark:text-slate-200">{model.display_name}</td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          model.provider === 'anthropic'
                            ? 'bg-orange-50 dark:bg-orange-950/20 text-orange-700 dark:text-orange-400'
                            : 'bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400'
                        }`}>
                          {model.provider === 'anthropic' ? 'Anthropic' : 'OpenRouter'}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-slate-500 dark:text-slate-400">{model.model_string}</td>
                      <td className="px-4 py-3.5">
                        <span className="text-xs text-slate-650 dark:text-slate-400 font-medium">
                          {model.input_price_per_million != null ? `$${Number(model.input_price_per_million).toFixed(2)}` : 'N/A'} / {model.output_price_per_million != null ? `$${Number(model.output_price_per_million).toFixed(2)}` : 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => handleToggleActive(model)}
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold cursor-pointer select-none transition-colors ${
                            model.is_active
                              ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-900/50'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200/50 dark:border-slate-700/50'
                          }`}
                        >
                          {model.is_active ? 'Active' : 'Inactive'}
                        </button>
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-2">
                        <button
                          onClick={() => {
                            setIsEditing(true);
                            setEditingModelId(model.id);
                            setDisplayName(model.display_name);
                            setProvider(model.provider);
                            setModelString(model.model_string);
                            setIsActive(model.is_active);
                            setInputPrice(model.input_price_per_million != null ? model.input_price_per_million.toString() : '');
                            setOutputPrice(model.output_price_per_million != null ? model.output_price_per_million.toString() : '');
                            setIsAddModalOpen(true);
                          }}
                          className="text-slate-500 hover:text-indigo-650 dark:text-slate-400 dark:hover:text-indigo-400 p-1"
                        >
                          <Edit className="w-4 h-4 inline" />
                        </button>
                        <button
                          onClick={() => handleDeleteModel(model.id)}
                          className="text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-450 p-1"
                        >
                          <Trash2 className="w-4 h-4 inline" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <hr className="border-slate-200 dark:border-slate-800 my-2" />

        <section className="border border-red-200 dark:border-red-950/60 rounded-xl p-6 bg-red-50 dark:bg-red-950/10 mb-10">
          <h2 className="text-lg font-semibold text-red-600 dark:text-red-400 mb-2 font-sora">Danger Zone</h2>
          <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
            <div>
              <p className="font-semibold text-slate-800 dark:text-slate-100">Delete Organisation</p>
              <p className="text-sm text-slate-600 dark:text-slate-400 max-w-lg mt-1">This will permanently delete your organisation, all members, documents, and data. This action cannot be undone.</p>
            </div>
            <button 
              onClick={() => setIsDeleteModalOpen(true)}
              className="w-fit shrink-0 px-4 py-2 bg-white dark:bg-slate-900 border border-red-500 text-red-600 dark:text-red-400 rounded-lg font-medium hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-700 dark:hover:text-red-300 transition-colors"
            >
              Delete Organisation
            </button>
          </div>
        </section>
      </div>

      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md p-6 text-center text-slate-800 dark:text-slate-100">
            <h3 className="text-xl font-semibold mb-2 text-red-600 dark:text-red-400 font-sora">Are you absolutely sure?</h3>
            <p className="text-slate-600 dark:text-slate-400 mb-6 text-sm">
              This action cannot be undone. Type your organisation name <span className="font-semibold text-slate-800 dark:text-slate-200">({orgName || 'the current name'})</span> to confirm deletion.
            </p>
            <input 
              type="text" 
              placeholder="Organisation Name" 
              value={deleteConfirmName} 
              onChange={e=>setDeleteConfirmName(e.target.value)}
              className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-red-100 dark:focus:ring-red-950/50 focus:border-red-500 dark:focus:border-red-400 outline-none transition-all mb-6 text-center text-slate-800 dark:text-slate-100" 
            />
            <div className="flex gap-3 w-full">
              <button onClick={() => { setIsDeleteModalOpen(false); setDeleteConfirmName(''); }} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-55 dark:hover:bg-slate-800 font-medium transition-colors">Cancel</button>
              <button 
                disabled={deleteConfirmName !== orgName || deleteMutation.isPending}
                onClick={handleDelete} 
                className="flex-1 py-2 rounded-lg bg-red-600 dark:bg-red-500 hover:bg-red-700 dark:hover:bg-red-400 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl w-full max-w-md p-6 text-slate-800 dark:text-slate-100">
            <h3 className="text-xl font-semibold mb-4 font-sora">{isEditing ? 'Edit Model' : 'Add Model'}</h3>
            <form onSubmit={handleSubmitModel} className="space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Display Name</label>
                <input
                  required
                  type="text"
                  placeholder="e.g. Claude 4.5 Haiku"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Provider</label>
                <select
                  value={provider}
                  onChange={e => setProvider(e.target.value as 'anthropic' | 'openrouter')}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Model Identifier String</label>
                <input
                  required
                  type="text"
                  placeholder="e.g. claude-haiku-4-5-20251001"
                  value={modelString}
                  onChange={e => setModelString(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all font-mono text-sm text-slate-800 dark:text-slate-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Input Price ($ / M tokens)</label>
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    placeholder="Leave blank to skip"
                    value={inputPrice}
                    onChange={e => setInputPrice(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Output Price ($ / M tokens)</label>
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    placeholder="Leave blank to skip"
                    value={outputPrice}
                    onChange={e => setOutputPrice(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                  />
                </div>
              </div>
              <p className="text-xs text-slate-550 dark:text-slate-400 -mt-2">
                Leave blank to use a rough fallback estimate.
              </p>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="is_active_checkbox"
                  checked={isActive}
                  onChange={e => setIsActive(e.target.checked)}
                  className="rounded border-slate-300 dark:border-slate-700 text-indigo-650 focus:ring-indigo-500 w-4 h-4 cursor-pointer"
                />
                <label htmlFor="is_active_checkbox" className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer select-none">
                  Model is Active and available for selection
                </label>
              </div>

              <div className="flex gap-3 w-full pt-4">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-650 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createModelMutation.isPending || updateModelMutation.isPending}
                  className="flex-1 py-2 rounded-lg bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-medium transition-colors disabled:opacity-50"
                >
                  {createModelMutation.isPending || updateModelMutation.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

