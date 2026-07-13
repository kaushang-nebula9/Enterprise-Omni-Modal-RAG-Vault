import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { Plus, Trash2, Edit, ChevronDown } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useNavigate } from 'react-router-dom';

export const OrganisationSettingsPage: React.FC = () => {
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  interface ProviderRegistryEntry {
    provider_id: string;
    display_name: string;
    sdk_type: string;
    requires_base_url: boolean;
    default_base_url?: string;
  }

  // Models CRUD state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  
  const [displayName, setDisplayName] = useState('');
  const [providerId, setProviderId] = useState('');
  const [modelName, setModelName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [inputCost, setInputCost] = useState('');
  const [outputCost, setOutputCost] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [tier, setTier] = useState<'fast' | 'balanced' | 'powerful'>('balanced');

  const [providers, setProviders] = useState<ProviderRegistryEntry[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderRegistryEntry | null>(null);

  // Custom provider select state
  const [isProviderDropdownOpen, setIsProviderDropdownOpen] = useState(false);
  const providerDropdownRef = React.useRef<HTMLDivElement>(null);

  // Custom tier select state
  const [isTierDropdownOpen, setIsTierDropdownOpen] = useState(false);
  const tierDropdownRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutsideProvider = (e: MouseEvent) => {
      if (providerDropdownRef.current && !providerDropdownRef.current.contains(e.target as Node)) {
        setIsProviderDropdownOpen(false);
      }
    };
    const handleClickOutsideTier = (e: MouseEvent) => {
      if (tierDropdownRef.current && !tierDropdownRef.current.contains(e.target as Node)) {
        setIsTierDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutsideProvider);
    document.addEventListener('mousedown', handleClickOutsideTier);
    return () => {
      document.removeEventListener('mousedown', handleClickOutsideProvider);
      document.removeEventListener('mousedown', handleClickOutsideTier);
    };
  }, []);

  // Custom default model select state
  const [isDefaultModelDropdownOpen, setIsDefaultModelDropdownOpen] = useState(false);
  const defaultModelDropdownRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutsideDefaultModel = (e: MouseEvent) => {
      if (defaultModelDropdownRef.current && !defaultModelDropdownRef.current.contains(e.target as Node)) {
        setIsDefaultModelDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutsideDefaultModel);
    return () => document.removeEventListener('mousedown', handleClickOutsideDefaultModel);
  }, []);

  useEffect(() => {
    const fetchProviders = async () => {
      setIsLoadingProviders(true);
      setProvidersError(null);
      try {
        const data = await adminService.getProviders();
        setProviders(data);
      } catch (err: any) {
        setProvidersError(err.message || 'Failed to fetch providers');
      } finally {
        setIsLoadingProviders(false);
      }
    };
    fetchProviders();
  }, []);

  const resetForm = () => {
    setDisplayName('');
    setProviderId('');
    setModelName('');
    setApiKey('');
    setBaseUrl('');
    setInputCost('');
    setOutputCost('');
    setSelectedProvider(null);
    setIsActive(true);
    setTier('balanced');
    setEditingModelId(null);
    setIsProviderDropdownOpen(false);
    setIsTierDropdownOpen(false);
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
      is_active: isActive,
      provider_id: providerId,
      base_url: selectedProvider?.requires_base_url ? baseUrl : null,
      input_cost_per_million_tokens: inputCost === '' ? null : parseFloat(inputCost),
      output_cost_per_million_tokens: outputCost === '' ? null : parseFloat(outputCost),
      model_name: modelName,
      api_key: apiKey,
      tier: tier,
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
                <div className="space-y-1 relative" ref={defaultModelDropdownRef}>
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Default Chat Model</label>
                  <button
                    type="button"
                    onClick={() => setIsDefaultModelDropdownOpen(!isDefaultModelDropdownOpen)}
                    className="w-full flex items-center justify-between px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 text-left outline-none transition-all"
                  >
                    <span>
                      {defaultModelId 
                        ? (modelsData?.find(m => m.id === defaultModelId)?.display_name || defaultModelId)
                        : "System Default (Oldest Active Anthropic Model)"}
                    </span>
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isDefaultModelDropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {isDefaultModelDropdownOpen && (
                    <div className="absolute left-0 right-0 mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto p-1 flex flex-col gap-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          setDefaultModelId('');
                          setIsDefaultModelDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                          defaultModelId === ''
                            ? "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-semibold"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        System Default (Oldest Active Anthropic Model)
                      </button>
                      {modelsData?.filter(m => m.is_active).map(m => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setDefaultModelId(m.id);
                            setIsDefaultModelDropdownOpen(false);
                          }}
                          className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                            defaultModelId === m.id
                              ? "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-semibold"
                              : "hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                          }`}
                        >
                          {m.display_name} ({m.display_name || m.model_name})
                        </button>
                      ))}
                    </div>
                  )}
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
                      <td className="px-4 py-3.5 font-medium text-slate-800 dark:text-slate-200">
                        <div className="flex items-center gap-2">
                          <span>{model.display_name}</span>
                          {model.tier && (
                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${
                              model.tier === 'fast'
                                ? 'bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-450 border-emerald-205/20 dark:border-emerald-900/50'
                                : model.tier === 'powerful'
                                ? 'bg-purple-50 dark:bg-purple-950/20 text-purple-700 dark:text-purple-400 border-purple-205/20 dark:border-purple-900/50'
                                : 'bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400 border-blue-205/20 dark:border-blue-900/50'
                            }`}>
                              {model.tier.charAt(0).toUpperCase() + model.tier.slice(1)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          model.provider_id === 'anthropic'
                            ? 'bg-orange-50 dark:bg-orange-950/20 text-orange-700 dark:text-orange-400'
                            : 'bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400'
                        }`}>
                          {providers.find(p => p.provider_id === model.provider_id)?.display_name || model.provider_id}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-slate-500 dark:text-slate-400">{model.model_name}</td>
                      <td className="px-4 py-3.5">
                        <span className="text-xs text-slate-650 dark:text-slate-400 font-medium">
                          {model.input_cost_per_million_tokens != null ? `$${Number(model.input_cost_per_million_tokens).toFixed(2)}` : 'N/A'} / {model.output_cost_per_million_tokens != null ? `$${Number(model.output_cost_per_million_tokens).toFixed(2)}` : 'N/A'}
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
                            setProviderId(model.provider_id || '');
                            const foundProv = providers.find(p => p.provider_id === model.provider_id);
                            setSelectedProvider(foundProv || null);
                            setModelName(model.model_name || '');
                            setApiKey(model.api_key || '');
                            setBaseUrl(model.base_url || '');
                            setIsActive(model.is_active);
                            setInputCost(model.input_cost_per_million_tokens != null ? model.input_cost_per_million_tokens.toString() : '');
                            setOutputCost(model.output_cost_per_million_tokens != null ? model.output_cost_per_million_tokens.toString() : '');
                            setTier(model.tier || 'balanced');
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
              {isLoadingProviders && (
                <div className="text-sm text-slate-500 dark:text-slate-400">Loading providers...</div>
              )}
              
              {providersError && (
                <div className="p-3 text-sm text-red-650 bg-red-50 dark:bg-red-950/20 dark:text-red-400 rounded-lg">
                  {providersError}
                </div>
              )}

              <div className="space-y-1 relative" ref={providerDropdownRef}>
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Provider</label>
                <button
                  type="button"
                  onClick={() => setIsProviderDropdownOpen(!isProviderDropdownOpen)}
                  className="w-full flex items-center justify-between px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100 text-left"
                >
                  <span className={providerId ? "text-slate-800 dark:text-slate-100" : "text-slate-400"}>
                    {providerId ? (providers.find(p => p.provider_id === providerId)?.display_name || providerId) : "Select a provider"}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isProviderDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isProviderDropdownOpen && (
                  <div className="absolute left-0 right-0 mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto p-1 flex flex-col gap-0.5">
                    {providers.map(p => (
                      <button
                        key={p.provider_id}
                        type="button"
                        onClick={() => {
                          setProviderId(p.provider_id);
                          setBaseUrl('');
                          setSelectedProvider(p);
                          setIsProviderDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                          providerId === p.provider_id
                            ? "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-semibold"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        {p.display_name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Display Name (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Our GPT-4o"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                />
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Friendly name shown across the app. Defaults to model name if left blank.
                </p>
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Model ID</label>
                <input
                  required
                  type="text"
                  placeholder="e.g. claude-haiku-4-5, gpt-4o, gemini-2.0-flash"
                  value={modelName}
                  onChange={e => setModelName(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                />
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Enter the exact model ID as listed by your provider.
                </p>
              </div>

              <div className="space-y-1 relative" ref={tierDropdownRef}>
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Model Tier</label>
                <button
                  type="button"
                  onClick={() => setIsTierDropdownOpen(!isTierDropdownOpen)}
                  className="w-full flex items-center justify-between px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100 text-left"
                >
                  <span className="text-slate-800 dark:text-slate-100 text-md">
                    {tier.charAt(0).toUpperCase() + tier.slice(1)}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isTierDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isTierDropdownOpen && (
                  <div className="absolute left-0 right-0 mt-1 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-850 rounded-lg shadow-lg z-50 p-1 flex flex-col gap-0.5 max-h-60 overflow-y-auto">
                    {[
                      { value: 'fast', label: 'Fast', desc: 'Lightweight and cheap. Best for simple lookups and short questions.' },
                      { value: 'balanced', label: 'Balanced', desc: 'General purpose. Handles summaries, comparisons, and multi-part questions.' },
                      { value: 'powerful', label: 'Powerful', desc: 'Complex reasoning, long context, and multi-condition analysis.' },
                    ].map(t => (
                      <button
                        key={t.value}
                        type="button"
                        onClick={() => {
                          setTier(t.value as 'fast' | 'balanced' | 'powerful');
                          setIsTierDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                          tier === t.value
                            ? "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-semibold"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        }`}
                      >
                        <div className="font-semibold text-sm">{t.label}</div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 font-normal mt-0.5 leading-normal">{t.desc}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">API Key</label>
                <input
                  required
                  type="password"
                  placeholder="Paste your API key here"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                />
              </div>

              {selectedProvider?.requires_base_url === true && (
                <div className="space-y-1">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Base URL</label>
                  <input
                    required
                    type="text"
                    placeholder="e.g. https://your-deployment.example.com/v1"
                    value={baseUrl}
                    onChange={e => setBaseUrl(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <div className='flex flex-col'>
                    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Input cost</label>
                    <label className="text-xs text-slate-500 dark:text-slate-400">(per 1M tokens, USD)</label>
                  </div>
                    
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    placeholder="e.g. 0.80"
                    value={inputCost}
                    onChange={e => setInputCost(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                  />
                </div>
                <div className="space-y-1">
                  <div className='flex flex-col'>
                    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Output cost</label>
                    <label className="text-xs text-slate-500 dark:text-slate-400">(per 1M tokens, USD)</label>
                  </div>
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    placeholder="e.g. 4.00"
                    value={outputCost}
                    onChange={e => setOutputCost(e.target.value)}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 outline-none transition-all text-slate-800 dark:text-slate-100"
                  />
                </div>
              </div>

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
                  className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-655 dark:text-slate-300 hover:bg-slate-55 dark:hover:bg-slate-800 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createModelMutation.isPending || updateModelMutation.isPending || isLoadingProviders || !!providersError}
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

