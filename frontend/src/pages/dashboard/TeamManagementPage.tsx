import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminService } from '../../services/adminService';
import { roleService } from '../../services/roleService';
import { useAuthStore } from '../../store/authStore';
import { MoreVertical, UserPlus, X } from 'lucide-react';
import api from '../../services/api'; // For invite

// We need an InviteMemberPayload that is currently handled via raw API or we can add it to adminService.
// Wait, inviteMember is in authService.
// Wait, `inviteMember` wasn't exported from authService in my previous check. Let me add it.
// I'll define it here temporarily if not present, but I should add it to authService.
import type { UserResponse, RoleResponse } from '../../types/auth';

const inviteMemberAPI = async (data: { full_name: string; email: string; role_id: string }) => {
  const response = await api.post('/api/v1/auth/invite-member', data);
  return response.data;
};

export const TeamManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  
  // Modals state for actions
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [deactivatingUserId, setDeactivatingUserId] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [dropdownOpenId, setDropdownOpenId] = useState<string | null>(null);

  const { data: members, isLoading: loadingMembers } = useQuery({
    queryKey: ['members'],
    queryFn: adminService.getMembers,
  });

  const { data: roles } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminService.updateMember(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setEditingUserId(null);
      setDeactivatingUserId(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setDeletingUserId(null);
    }
  });

  // Invite Form State
  const [inviteName, setInviteName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('');
  const [inviteStatus, setInviteStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteStatus(null);
    try {
      await inviteMemberAPI({ full_name: inviteName, email: inviteEmail, role_id: inviteRole });
      setInviteStatus({ type: 'success', msg: 'Invite sent successfully' });
      setInviteName('');
      setInviteEmail('');
      setInviteRole('');
      setTimeout(() => setIsInviteModalOpen(false), 2000);
    } catch (err: any) {
      setInviteStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to send invite' });
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-6xl mx-auto h-full text-slate-800 dark:text-slate-100">
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-semibold font-sora text-slate-800 dark:text-slate-100">Team Management</h1>
          <p className="text-slate-500 dark:text-slate-400">Manage your organisation's members and their roles.</p>
        </div>
        <button 
          onClick={() => setIsInviteModalOpen(true)}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white px-4 py-2 rounded-lg transition-colors font-medium"
        >
          <UserPlus className="w-4 h-4" />
          Invite Member
        </button>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm flex-1 flex flex-col">
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 text-sm">
              <tr>
                <th className="px-6 py-4 font-medium">Member</th>
                <th className="px-6 py-4 font-medium">Role</th>
                <th className="px-6 py-4 font-medium">Status</th>
                <th className="px-6 py-4 font-medium">Joined</th>
                <th className="px-6 py-4 font-medium w-16"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {loadingMembers ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 dark:text-slate-500">Loading members...</td>
                </tr>
              ) : members?.map((m: UserResponse) => (
                <tr key={m.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 flex items-center justify-center font-bold text-sm shrink-0 overflow-hidden">
                        {m.avatar_url ? (
                          <img src={m.avatar_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          m.full_name.substring(0, 2).toUpperCase()
                        )}
                      </div>
                      <div>
                        <div className="font-medium text-slate-900 dark:text-slate-200">{m.full_name} {m.id === currentUser?.id && '(You)'}</div>
                        <div className="text-sm text-slate-500 dark:text-slate-450">{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-block bg-indigo-100 dark:bg-indigo-950/60 text-indigo-755 dark:text-indigo-400 rounded-full px-3 py-1 text-xs font-medium">
                      {m.role.name}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {m.is_active ? (
                      <span className="inline-block bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 rounded-full px-3 py-1 text-xs font-medium">Active</span>
                    ) : (
                      <span className="inline-block bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-400 rounded-full px-3 py-1 text-xs font-medium">Inactive</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 relative">
                    <button 
                      onClick={() => setDropdownOpenId(dropdownOpenId === m.id ? null : m.id)}
                      className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-105 dark:hover:bg-slate-800 rounded-lg transition-colors"
                    >
                      <MoreVertical className="w-5 h-5" />
                    </button>
                    {dropdownOpenId === m.id && (
                      <div className="absolute right-6 top-10 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-lg rounded-lg py-1 z-10">
                        <button 
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => { setEditingUserId(m.id); setDropdownOpenId(null); }}
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Change Role
                        </button>
                        <button 
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => { setDeactivatingUserId(m.id); setDropdownOpenId(null); }}
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {m.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button 
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => { setDeletingUserId(m.id); setDropdownOpenId(null); }}
                          className="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Remove Member
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite Modal */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200 text-slate-800 dark:text-slate-100">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-xl font-semibold font-sora">Invite Member</h2>
              <button onClick={() => setIsInviteModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><X className="w-5 h-5"/></button>
            </div>
            <form onSubmit={handleInvite} className="p-6 flex flex-col gap-4">
              {inviteStatus && (
                <div className={`p-3 rounded-lg text-sm ${inviteStatus.type === 'success' ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-900/50' : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900/50'}`}>
                  {inviteStatus.msg}
                </div>
              )}
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Full Name</label>
                <input required value={inviteName} onChange={e=>setInviteName(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Email Address</label>
                <input required type="email" value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Role</label>
                <select required value={inviteRole} onChange={e=>setInviteRole(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none bg-white transition-all">
                  <option value="">Select a role...</option>
                  {roles?.map((r: RoleResponse) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <button type="submit" className="mt-2 w-full bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors">
                Send Invite
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deletingUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center text-slate-800 dark:text-slate-100">
            <h3 className="text-lg font-semibold mb-2">Remove Member</h3>
            <p className="text-slate-500 dark:text-slate-400 mb-6">Are you sure you want to permanently remove this member? This action cannot be undone.</p>
            <div className="flex gap-3 w-full">
              <button onClick={() => setDeletingUserId(null)} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-750 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors">Cancel</button>
              <button onClick={() => deleteMutation.mutate(deletingUserId)} className="flex-1 py-2 rounded-lg bg-red-655 dark:bg-red-600 hover:bg-red-700 dark:hover:bg-red-500 text-white font-medium transition-colors">Remove</button>
            </div>
          </div>
        </div>
      )}

      {/* Deactivate/Activate Confirmation */}
      {deactivatingUserId && (() => {
        const target = members?.find(m => m.id === deactivatingUserId);
        const newStatus = !target?.is_active;
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center text-slate-800 dark:text-slate-100">
              <h3 className="text-lg font-semibold mb-2">{newStatus ? 'Activate' : 'Deactivate'} Member</h3>
              <p className="text-slate-500 dark:text-slate-400 mb-6">Are you sure you want to {newStatus ? 'activate' : 'deactivate'} this member?</p>
              <div className="flex gap-3 w-full">
                <button onClick={() => setDeactivatingUserId(null)} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-750 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors">Cancel</button>
                <button onClick={() => updateMutation.mutate({ id: deactivatingUserId, data: { is_active: newStatus }})} className="flex-1 py-2 rounded-lg bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-medium transition-colors">Confirm</button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Change Role Modal */}
      {editingUserId && (() => {
        const target = members?.find(m => m.id === editingUserId);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md p-6 text-slate-800 dark:text-slate-100">
              <h3 className="text-lg font-semibold mb-4">Change Role</h3>
              <div className="space-y-1 mb-6">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Select Role</label>
                <select 
                  defaultValue={target?.role_id}
                  id="roleSelect"
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-100"
                >
                  {roles?.map((r: RoleResponse) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div className="flex gap-3 w-full">
                <button onClick={() => setEditingUserId(null)} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-750 bg-white dark:bg-slate-900 text-slate-650 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors">Cancel</button>
                <button 
                  onClick={() => {
                    const el = document.getElementById('roleSelect') as HTMLSelectElement;
                    if (el) updateMutation.mutate({ id: editingUserId, data: { role_id: el.value } });
                  }} 
                  className="flex-1 py-2 rounded-lg bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white font-medium transition-colors"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
