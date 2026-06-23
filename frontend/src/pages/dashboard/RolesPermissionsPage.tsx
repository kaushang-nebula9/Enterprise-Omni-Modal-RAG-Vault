import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { roleService } from '../../services/roleService';
import type { RoleResponse } from '../../types/auth';
import { ShieldPlus, Edit2, Trash2, X } from 'lucide-react';

export const RolesPermissionsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { data: roles, isLoading } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  });

  const createMutation = useMutation({
    mutationFn: roleService.createRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setIsCreateOpen(false);
      setNewRoleName('');
      setNewParentRoleId(null);
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; parent_role_id?: string | null } }) => roleService.updateRole(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setEditingRole(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: roleService.deleteRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setDeletingRole(null);
    }
  });

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newParentRoleId, setNewParentRoleId] = useState<string | null>(null);

  const [editingRole, setEditingRole] = useState<RoleResponse | null>(null);
  const [editParentRoleId, setEditParentRoleId] = useState<string | null>(null);
  const [deletingRole, setDeletingRole] = useState<RoleResponse | null>(null);

  useEffect(() => {
    if (editingRole) {
      setEditParentRoleId(editingRole.parent_role_id ?? null);
    }
  }, [editingRole]);

  const editExcludedIds = useMemo(() => {
    if (!editingRole || !roles) return new Set<string>();
    const excluded = new Set<string>([editingRole.id]);
    const addDescendants = (parentId: string) => {
      for (const r of roles) {
        if (r.parent_role_id === parentId && !excluded.has(r.id)) {
          excluded.add(r.id);
          addDescendants(r.id);
        }
      }
    };
    addDescendants(editingRole.id);
    return excluded;
  }, [editingRole, roles]);

  return (
    <div className="flex flex-col gap-6 w-full max-w-6xl mx-auto h-full text-slate-800 dark:text-slate-100">
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-semibold font-sora text-slate-800 dark:text-slate-100">Roles and Permissions</h1>
          <p className="text-slate-500 dark:text-slate-400">Define roles for your organisation. Document access is configured per document during upload.</p>
        </div>
        <button 
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white px-4 py-2 rounded-lg transition-colors font-medium"
        >
          <ShieldPlus className="w-4 h-4" />
          Create Role
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 rounded-full border-4 border-indigo-200 dark:border-indigo-950 border-t-indigo-700 dark:border-t-indigo-500 animate-spin"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-12">
          {roles
            ?.filter((role: RoleResponse) => role.name.toLowerCase() !== 'admin' && role.name.toLowerCase() !== 'member')
            .map((role: RoleResponse) => (
              <div key={role.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4">
                <div className="flex justify-between items-start">
                  <div className="flex flex-col gap-1">
                    <span className="font-semibold text-slate-800 dark:text-slate-100 text-lg">{role.name}</span>
                    {role.parent_role_id && (() => {
                      const parentRole = roles?.find((r: RoleResponse) => r.id === role.parent_role_id);
                      return parentRole ? (
                        <span className="text-sm text-slate-500 dark:text-slate-400">↳ Reports to: {parentRole.name}</span>
                      ) : null;
                    })()}
                    {role.is_admin && (
                      <span className="inline-block bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-405 rounded-full px-3 py-1 text-xs font-medium w-fit mt-1">Admin Role</span>
                    )}
                    {role.is_default && !role.is_admin && (
                      <span className="inline-block bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-full px-3 py-1 text-xs font-medium w-fit mt-1">Default Role</span>
                    )}
                  </div>
                  {!role.is_default && (
                    <div className="flex gap-2 text-slate-400 dark:text-slate-500">
                      <button onClick={() => setEditingRole(role)} className="p-2 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 rounded-lg transition-colors"><Edit2 className="w-4 h-4" /></button>
                      <button onClick={() => setDeletingRole(role)} className="p-2 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  )}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Create Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200 text-slate-800 dark:text-slate-100">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold font-sora text-slate-800 dark:text-slate-100">Create Role</h2>
              <button onClick={() => setIsCreateOpen(false)} className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"><X className="w-5 h-5"/></button>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate({ name: newRoleName, parent_role_id: newParentRoleId || null }); }} className="p-6 flex flex-col gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Role Name</label>
                <input required autoFocus value={newRoleName} onChange={e=>setNewRoleName(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Parent Role</label>
                <select value={newParentRoleId ?? ''} onChange={e => setNewParentRoleId(e.target.value || null)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all">
                  <option value="">None (Top-level role)</option>
                  {roles?.map((role: RoleResponse) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={createMutation.isPending} className="mt-2 w-full bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50">
                {createMutation.isPending ? 'Creating...' : 'Create Role'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200 text-slate-800 dark:text-slate-100">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold font-sora text-slate-800 dark:text-slate-100">Edit Role</h2>
              <button onClick={() => setEditingRole(null)} className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"><X className="w-5 h-5"/></button>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); updateMutation.mutate({ id: editingRole.id, data: { name: editingRole.name, parent_role_id: editParentRoleId || null } }); }} className="p-6 flex flex-col gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Role Name</label>
                <input required autoFocus value={editingRole.name} onChange={e=>setEditingRole({ ...editingRole, name: e.target.value })} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Parent Role</label>
                <select value={editParentRoleId ?? ''} onChange={e => setEditParentRoleId(e.target.value || null)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all">
                  <option value="">None (Top-level role)</option>
                  {roles?.filter((role: RoleResponse) => !editExcludedIds.has(role.id)).map((role: RoleResponse) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </div>
              <button type="submit" disabled={updateMutation.isPending} className="mt-2 w-full bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50">
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deletingRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center text-slate-800 dark:text-slate-100">
            <h3 className="text-lg font-semibold mb-2 text-slate-800 dark:text-slate-100">Delete Role</h3>
            <p className="text-slate-500 dark:text-slate-400 mb-6">Are you sure you want to delete the role <span className="font-semibold text-slate-800 dark:text-slate-200">{deletingRole.name}</span>? This action cannot be undone.</p>
            <div className="flex gap-3 w-full">
              <button onClick={() => setDeletingRole(null)} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors">Cancel</button>
              <button onClick={() => deleteMutation.mutate(deletingRole.id)} disabled={deleteMutation.isPending} className="flex-1 py-2 rounded-lg bg-red-600 dark:bg-red-500 hover:bg-red-700 dark:hover:bg-red-400 text-white font-medium transition-colors disabled:opacity-50">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

