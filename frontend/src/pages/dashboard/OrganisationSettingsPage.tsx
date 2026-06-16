import React, { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { useAuthStore } from '../../store/authStore';
import { useNavigate } from 'react-router-dom';

export const OrganisationSettingsPage: React.FC = () => {
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const [orgName, setOrgName] = useState('');
  const [orgWebsite, setOrgWebsite] = useState('');
  const [updateStatus, setUpdateStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  const { data: orgData } = useQuery({
    queryKey: ['organisation'],
    queryFn: adminService.getOrganisation,
  });

  useEffect(() => {
    if (orgData) {
      setOrgName(orgData.name);
      setOrgWebsite(orgData.website || '');
    }
  }, [orgData]);

  // We don't have tenant name in user response currently, so we might fetch it or just use what we know. 
  // Wait, UserResponse has tenant_id but not tenant object. Let's just leave it blank initially or require fetching.
  // Actually, we can fetch tenant info via a new endpoint or just use orgName state for now.
  // Let's rely on the update payload.

  const updateMutation = useMutation({
    mutationFn: adminService.updateOrganisation,
    onSuccess: (data) => {
      setUpdateStatus({ type: 'success', msg: 'Organisation updated successfully' });
      setOrgName(data.name);
      setOrgWebsite(data.website || '');
      setTimeout(() => setUpdateStatus(null), 3000);
    },
    onError: (err: any) => {
      setUpdateStatus({ type: 'error', msg: err.response?.data?.detail || 'Update failed' });
    }
  });

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({ name: orgName, website: orgWebsite });
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
    <div className="flex flex-col gap-8 w-full max-w-4xl mx-auto h-full pb-12">
      <div className="shrink-0">
        <h1 className="text-2xl font-semibold font-sora text-slate-800">Organisation Settings</h1>
      </div>

      <div className="flex flex-col gap-6">
        <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800 mb-4 font-sora">General</h2>
          <form onSubmit={handleUpdate} className="flex flex-col gap-4 max-w-md">
            {updateStatus && (
              <div className={`p-3 rounded-lg text-sm ${updateStatus.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                {updateStatus.msg}
              </div>
            )}
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Organisation Name</label>
              <input required value={orgName} onChange={e=>setOrgName(e.target.value)} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-700">Website</label>
              <input type="url" value={orgWebsite} onChange={e=>setOrgWebsite(e.target.value)} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all" />
            </div>
            <button type="submit" disabled={updateMutation.isPending} className="mt-2 w-fit px-6 bg-indigo-700 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 transition-colors disabled:opacity-50">
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </form>
        </section>

        <hr className="border-slate-200 my-2" />

        <section className="border border-red-200 rounded-xl p-6 bg-red-50">
          <h2 className="text-lg font-semibold text-red-600 mb-2 font-sora">Danger Zone</h2>
          <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
            <div>
              <p className="font-semibold text-slate-800">Delete Organisation</p>
              <p className="text-sm text-slate-600 max-w-lg mt-1">This will permanently delete your organisation, all members, documents, and data. This action cannot be undone.</p>
            </div>
            <button 
              onClick={() => setIsDeleteModalOpen(true)}
              className="w-fit shrink-0 px-4 py-2 bg-white border border-red-500 text-red-600 rounded-lg font-medium hover:bg-red-50 hover:text-red-700 transition-colors"
            >
              Delete Organisation
            </button>
          </div>
        </section>
      </div>

      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 text-center">
            <h3 className="text-xl font-semibold mb-2 text-red-600 font-sora">Are you absolutely sure?</h3>
            <p className="text-slate-600 mb-6 text-sm">
              This action cannot be undone. Type your organisation name <span className="font-semibold">({orgName || 'the current name'})</span> to confirm deletion.
            </p>
            <input 
              type="text" 
              placeholder="Organisation Name" 
              value={deleteConfirmName} 
              onChange={e=>setDeleteConfirmName(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-100 focus:border-red-500 outline-none transition-all mb-6 text-center" 
            />
            <div className="flex gap-3 w-full">
              <button onClick={() => { setIsDeleteModalOpen(false); setDeleteConfirmName(''); }} className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium transition-colors">Cancel</button>
              <button 
                disabled={deleteConfirmName !== orgName || deleteMutation.isPending}
                onClick={handleDelete} 
                className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
