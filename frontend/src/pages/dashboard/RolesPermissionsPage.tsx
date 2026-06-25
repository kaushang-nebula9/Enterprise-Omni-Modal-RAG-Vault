import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { roleService } from '../../services/roleService';
import { departmentService } from '../../services/departmentService';
import type { RoleResponse } from '../../types/auth';
import { ShieldPlus, Edit2, Trash2, X, Search, ChevronDown, LayoutList, GitBranch } from 'lucide-react';
import { RoleHierarchyTree } from '../../components/dashboard/RoleHierarchyTree';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export const RolesPermissionsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const location = useLocation();
  const { data: roles, isLoading } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  });

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: departmentService.getDepartments,
  });

  const {
    data: treeData = [],
    isLoading: isTreeLoading,
    isError: isTreeError,
  } = useQuery({
    queryKey: ['rolesTree'],
    queryFn: roleService.getRolesTree,
  });

  const createMutation = useMutation({
    mutationFn: roleService.createRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['rolesTree'] });
      setIsCreateOpen(false);
      setNewRoleName('');
      setNewParentRoleId(null);
      setNewDepartmentId(null);
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; parent_role_id?: string | null; department_id?: string | null } }) => roleService.updateRole(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['rolesTree'] });
      setEditingRole(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: roleService.deleteRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['rolesTree'] });
      setDeletingRole(null);
    }
  });

  const [activeTab, setActiveTab] = useState<'list' | 'hierarchy'>('list');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newParentRoleId, setNewParentRoleId] = useState<string | null>(null);
  const [newDepartmentId, setNewDepartmentId] = useState<string | null>(null);

  useEffect(() => {
    if (location.state?.openCreate) {
      setIsCreateOpen(true);
    }
  }, [location]);

  const [search, setSearch] = useState('');
  const [filterDept, setFilterDept] = useState('all');
  const [filterRoleType, setFilterRoleType] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [editingRole, setEditingRole] = useState<RoleResponse | null>(null);
  const [editParentRoleId, setEditParentRoleId] = useState<string | null>(null);
  const [editDepartmentId, setEditDepartmentId] = useState<string | null>(null);
  const [deletingRole, setDeletingRole] = useState<RoleResponse | null>(null);

  useEffect(() => {
    if (editingRole) {
      setEditParentRoleId(editingRole.parent_role_id ?? null);
      setEditDepartmentId(editingRole.department_id ?? null);
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

  const filteredRoles = useMemo(() => {
    return roles?.filter((role: RoleResponse) => {
      if (role.name.toLowerCase() === 'admin' || role.name.toLowerCase() === 'member') return false;
      if (search && !role.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (filterDept !== 'all') {
        if (filterDept === 'unassigned') {
          if (role.department_id) return false;
        } else if (role.department_id !== filterDept) {
          return false;
        }
      }
      if (filterRoleType !== 'all') {
        if (filterRoleType === 'admin') {
          if (!role.is_admin) return false;
        } else if (filterRoleType === 'default') {
          if (!role.is_default) return false;
        } else if (filterRoleType === 'custom') {
          if (role.is_admin || role.is_default) return false;
        }
      }
      if (startDate || endDate) {
        const createdDate = new Date(role.created_at);
        createdDate.setHours(0, 0, 0, 0);

        if (startDate) {
          const start = new Date(startDate);
          start.setHours(0, 0, 0, 0);
          if (createdDate < start) return false;
        }
        
        if (endDate) {
          const end = new Date(endDate);
          end.setHours(23, 59, 59, 999);
          if (createdDate > end) return false;
        }
      }
      return true;
    }) ?? [];
  }, [roles, search, filterDept, filterRoleType, startDate, endDate]);

  return (
    <div className="space-y-6 text-slate-800 dark:text-slate-100 animate-in fade-in duration-300">
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Roles and Permissions</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Define roles for your organisation. Document access is configured per document during upload.</p>
        </div>
        <button 
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-850 dark:hover:bg-indigo-600 text-white px-4 py-2.5 rounded-xl transition-colors font-semibold shadow"
        >
          <ShieldPlus className="w-4 h-4" />
          Create Role
        </button>
      </div>

      {/* Tab Toggle */}
      <div className="flex items-center gap-1 rounded-xl w-fit">
        <button
          id="tab-list-view"
          onClick={() => setActiveTab('list')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
            activeTab === 'list'
              ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-400 shadow-sm border border-slate-200 dark:border-slate-700'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          <LayoutList className="w-4 h-4" />
          List View
        </button>
        <button
          id="tab-hierarchy-view"
          onClick={() => setActiveTab('hierarchy')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
            activeTab === 'hierarchy'
              ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-400 shadow-sm border border-slate-200 dark:border-slate-700'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          <GitBranch className="w-4 h-4" />
          Hierarchy View
        </button>
      </div>

      {/* ── Hierarchy View ── */}
      {activeTab === 'hierarchy' && (
        <RoleHierarchyTree
          treeData={treeData}
          isLoading={isTreeLoading}
          isError={isTreeError}
        />
      )}

      {/* ── List View: Filters & Search ── */}
      {activeTab === 'list' && (
      <>
      <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full flex-1 min-w-[200px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
          <input
            id="role-search"
            type="text"
            placeholder="Search roles by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 focus:bg-white dark:focus:bg-slate-900 transition-all"
          />
        </div>

        <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 mx-1 shrink-0"></div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-end gap-3 w-full lg:w-auto shrink-0">
          {/* Department Filter */}
          <div className="relative shrink-0">
            <select
              value={filterDept}
              onChange={(e) => {
                setFilterDept(e.target.value);
                e.target.blur();
              }}
              className="peer appearance-none w-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <option value="all">All Departments</option>
              <option value="unassigned">Unassigned</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>{dept.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
          </div>

          {/* Role Type Filter */}
          <div className="relative shrink-0">
            <select
              value={filterRoleType}
              onChange={(e) => {
                setFilterRoleType(e.target.value);
                e.target.blur();
              }}
              className="peer appearance-none w-36 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <option value="all">All Types</option>
              <option value="admin">Admin Roles</option>
              <option value="default">Default Roles</option>
              <option value="custom">Custom Roles</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
          </div>

          {/* Date Range */}
          <div className="flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-2 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-within:ring-2 focus-within:ring-indigo-400 dark:focus-within:ring-indigo-500 focus-within:bg-white dark:focus-within:bg-slate-900 overflow-hidden">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 dark:text-slate-300 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="Start Date"
            />
            <span className="text-slate-300 dark:text-slate-600 font-medium px-1">-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent text-sm text-slate-700 dark:text-slate-300 font-medium py-2 focus:outline-none cursor-pointer w-[115px]"
              title="End Date"
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 rounded-full border-4 border-indigo-200 dark:border-indigo-950 border-t-indigo-700 dark:border-t-indigo-500 animate-spin"></div>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden mb-12">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Role Name</th>
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Reports To</th>
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Department</th>
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Created At</th>
                  <th className="px-4 py-3.5 text-right font-semibold text-slate-600 dark:text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredRoles.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center text-slate-400 dark:text-slate-500 py-16">
                      <div className="flex flex-col items-center gap-3">
                        <ShieldPlus className="w-12 h-12 text-slate-200 dark:text-slate-800" />
                        <p className="font-medium text-slate-500 dark:text-slate-400">No roles match your search or filters</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredRoles.map((role: RoleResponse) => {
                    const parentRole = role.parent_role_id
                      ? roles?.find((r: RoleResponse) => r.id === role.parent_role_id)
                      : null;
                    return (
                      <tr
                        key={role.id}
                        className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors"
                      >
                        {/* Role Name */}
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-800 dark:text-slate-200">{role.name}</span>
                            {role.is_admin && (
                              <span className="inline-block bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 rounded-full px-2 py-0.5 text-[10px] font-medium">Admin</span>
                            )}
                            {role.is_default && !role.is_admin && (
                              <span className="inline-block bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-full px-2 py-0.5 text-[10px] font-medium">Default</span>
                            )}
                          </div>
                        </td>

                        {/* Reports To */}
                        <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                          {parentRole ? (
                            <span className="text-sm">↳ {parentRole.name}</span>
                          ) : (
                            <span className="text-xs italic text-slate-400 dark:text-slate-550">Top-level role</span>
                          )}
                        </td>

                        {/* Department */}
                        <td className="px-4 py-3.5">
                          {role.department_name ? (
                            <span className="inline-block bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 rounded-full px-2.5 py-1 text-xs font-semibold">
                              {role.department_name}
                            </span>
                          ) : (
                            <span className="text-xs italic text-slate-400 dark:text-slate-550">Unassigned</span>
                          )}
                        </td>

                        {/* Created At */}
                        <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                          {formatDate(role.created_at)}
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3.5">
                          <div className="flex items-center justify-end gap-1">
                            {!role.is_default ? (
                              <>
                                <button
                                  onClick={() => setEditingRole(role)}
                                  title="Edit Role"
                                  className="p-2 text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 rounded-lg transition-colors"
                                >
                                  <Edit2 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => setDeletingRole(role)}
                                  title="Delete Role"
                                  className="p-2 text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </>
                            ) : (
                              <span className="text-xs text-slate-400 dark:text-slate-500 italic px-2">System default</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  }))}
              </tbody>
            </table>
          </div>

          {/* Footer count */}
          {!isLoading && filteredRoles.length > 0 && (
            <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950">
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Showing {filteredRoles.length} of {roles?.filter((role: RoleResponse) => role.name.toLowerCase() !== 'admin' && role.name.toLowerCase() !== 'member').length || 0} role{roles?.filter((role: RoleResponse) => role.name.toLowerCase() !== 'admin' && role.name.toLowerCase() !== 'member').length !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>
      )}
      </>
      )}
      {/* end list view */}

      {/* Create Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200 text-slate-800 dark:text-slate-100">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold font-sora text-slate-800 dark:text-slate-100">Create Role</h2>
              <button onClick={() => setIsCreateOpen(false)} className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"><X className="w-5 h-5"/></button>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate({ name: newRoleName, parent_role_id: newParentRoleId || null, department_id: newDepartmentId || null }); }} className="p-6 flex flex-col gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-330">Role Name</label>
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
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Department</label>
                <select value={newDepartmentId ?? ''} onChange={e => setNewDepartmentId(e.target.value || null)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all">
                  <option value="">Unassigned</option>
                  {departments?.map((dept) => (
                    <option key={dept.id} value={dept.id}>{dept.name}</option>
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
            <form onSubmit={(e) => { e.preventDefault(); updateMutation.mutate({ id: editingRole.id, data: { name: editingRole.name, parent_role_id: editParentRoleId || null, department_id: editDepartmentId || null } }); }} className="p-6 flex flex-col gap-4">
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
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Department</label>
                <select value={editDepartmentId ?? ''} onChange={e => setEditDepartmentId(e.target.value || null)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all">
                  <option value="">Unassigned</option>
                  {departments?.map((dept) => (
                    <option key={dept.id} value={dept.id}>{dept.name}</option>
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

