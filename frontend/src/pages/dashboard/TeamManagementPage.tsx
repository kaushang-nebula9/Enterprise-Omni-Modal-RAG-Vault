import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { adminService } from '../../services/adminService';
import { roleService } from '../../services/roleService';
import { departmentService } from '../../services/departmentService';
import { useAuthStore } from '../../store/authStore';
import {
  UserPlus,
  X,
  Search,
  ChevronDown,
  UserMinus,
  UserCheck,
  Users,
  Pencil,
  Trash2,
  AlertTriangle,
  Building2,
  Plus
} from 'lucide-react';
import api from '../../services/api'; // For invite
import type { UserResponse, RoleResponse } from '../../types/auth';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const inviteMemberAPI = async (data: { full_name: string; email: string; role_id: string }) => {
  const response = await api.post('/api/v1/auth/invite-member', data);
  return response.data;
};

export const TeamManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const location = useLocation();
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  
  // Modals state for actions
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [modalRoleId, setModalRoleId] = useState('');
  const [modalDeptId, setModalDeptId] = useState('');
  const [deactivatingUserId, setDeactivatingUserId] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  // Search & Filter State
  const [search, setSearch] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data: members = [], isLoading: loadingMembers } = useQuery({
    queryKey: ['members'],
    queryFn: adminService.getMembers,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  });

  function handleSuccess(message: string) {
    queryClient.invalidateQueries({ queryKey: ['members'] });
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(null), 4000);
  }

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminService.updateMember(id, data),
    onSuccess: (_data, variables) => {
      void _data;
      setEditingUserId(null);
      setDeactivatingUserId(null);
      if (variables.data.role_id) {
        handleSuccess('Member role updated successfully');
      } else if (variables.data.is_active !== undefined) {
        handleSuccess(`Member ${variables.data.is_active ? 'activated' : 'deactivated'} successfully`);
      } else {
        handleSuccess('Member updated successfully');
      }
    }
  });

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteMember,
    onSuccess: () => {
      setDeletingUserId(null);
      handleSuccess('Member removed successfully');
    }
  });

  const updateRoleDeptMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; parent_role_id?: string | null; department_id?: string | null } }) =>
      roleService.updateRole(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.invalidateQueries({ queryKey: ['members'] });
    }
  });

  const targetMember = useMemo(() => {
    return members?.find((m: UserResponse) => m.id === editingUserId);
  }, [members, editingUserId]);

  useEffect(() => {
    if (targetMember) {
      setModalRoleId(targetMember.role_id);
      setModalDeptId(targetMember.role?.department_id || '');
    }
  }, [targetMember]);

  // Department State & Queries
  const { data: departments = [], isLoading: loadingDepartments } = useQuery({
    queryKey: ['departments'],
    queryFn: departmentService.getDepartments,
  });

  const [isDeptModalOpen, setIsDeptModalOpen] = useState(false);
  const [deptModalType, setDeptModalType] = useState<'create' | 'edit'>('create');
  const [editingDeptId, setEditingDeptId] = useState<string | null>(null);
  const [deptNameInput, setDeptNameInput] = useState('');
  const [deletingDeptId, setDeletingDeptId] = useState<string | null>(null);

  useEffect(() => {
    if (location.state?.openInvite) {
      setIsInviteModalOpen(true);
    }
    if (location.state?.openCreateDept) {
      setIsDeptModalOpen(true);
      setDeptModalType('create');
      setDeptNameInput('');
    }
  }, [location]);

  const createDeptMutation = useMutation({
    mutationFn: departmentService.createDepartment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      setIsDeptModalOpen(false);
      setDeptNameInput('');
      handleSuccess('Department created successfully');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to create department');
    }
  });

  const updateDeptMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string } }) => departmentService.updateDepartment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setIsDeptModalOpen(false);
      setDeptNameInput('');
      setEditingDeptId(null);
      handleSuccess('Department updated successfully');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to update department');
    }
  });

  const deleteDeptMutation = useMutation({
    mutationFn: departmentService.deleteDepartment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setDeletingDeptId(null);
      handleSuccess('Department deleted successfully');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to delete department');
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
      handleSuccess('Member invited successfully');
      setTimeout(() => setIsInviteModalOpen(false), 2000);
    } catch (err: any) {
      setInviteStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to send invite' });
    }
  };

  const filteredMembers = useMemo(() => {
    return members.filter((m: UserResponse) => {
      // 1. Search name or email
      if (search) {
        const query = search.toLowerCase();
        const matchesName = m.full_name?.toLowerCase().includes(query);
        const matchesEmail = m.email?.toLowerCase().includes(query);
        if (!matchesName && !matchesEmail) return false;
      }
      
      // 2. Role filter
      if (filterRole !== 'all' && m.role.id !== filterRole) return false;

      // 3. Status filter
      if (filterStatus !== 'all') {
        const isActive = filterStatus === 'active';
        if (m.is_active !== isActive) return false;
      }

      // 4. Date filter
      if (startDate || endDate) {
        const joinedDate = new Date(m.created_at);
        joinedDate.setHours(0, 0, 0, 0);

        if (startDate) {
          const start = new Date(startDate);
          start.setHours(0, 0, 0, 0);
          if (joinedDate < start) return false;
        }
        
        if (endDate) {
          const end = new Date(endDate);
          end.setHours(23, 59, 59, 999);
          if (joinedDate > end) return false;
        }
      }

      return true;
    });
  }, [members, search, filterRole, filterStatus, startDate, endDate]);

  return (
    <div className="space-y-6 text-slate-800 dark:text-slate-100 animate-in fade-in duration-300">
      {/* Success toast */}
      {successMessage && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium animate-fade-in">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {successMessage}
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Team Management</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Manage your organisation's members and their roles</p>
        </div>
        <button
          onClick={() => setIsInviteModalOpen(true)}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors shadow-sm"
        >
          <UserPlus className="w-4 h-4" />
          Invite Member
        </button>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full flex-1 min-w-[200px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
          <input
            id="member-search"
            type="text"
            placeholder="Search members by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 focus:bg-white dark:focus:bg-slate-900 transition-all"
          />
        </div>

        <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 mx-1 shrink-0"></div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-end gap-3 w-full lg:w-auto shrink-0">
          {/* Role Filter */}
          <div className="relative shrink-0">
            <select
              value={filterRole}
              onChange={(e) => {
                setFilterRole(e.target.value);
                e.target.blur();
              }}
              className="peer appearance-none w-32 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <option value="all">All Roles</option>
              {roles.map((r: RoleResponse) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
          </div>

          {/* Status Filter */}
          <div className="relative shrink-0">
            <select
              value={filterStatus}
              onChange={(e) => {
                setFilterStatus(e.target.value);
                e.target.blur();
              }}
              className="peer appearance-none w-36 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
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

      {/* Table */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Member</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Role</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Department</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Status</th>
                <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Joined</th>
                <th className="px-4 py-3.5 text-right font-semibold text-slate-600 dark:text-slate-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {loadingMembers ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-4">
                        <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" style={{ width: `${60 + (j * 13) % 40}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filteredMembers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-16 text-center text-slate-400 dark:text-slate-500">
                    <div className="flex flex-col items-center gap-3">
                      <Users className="w-12 h-12 text-slate-200 dark:text-slate-800" />
                      <div>
                        <p className="font-medium text-slate-500 dark:text-slate-400">
                          {search ? 'No members match your search' : 'No members yet'}
                        </p>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredMembers.map((m: UserResponse) => (
                  <tr
                    key={m.id}
                    className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    {/* Member */}
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 flex items-center justify-center font-bold text-sm shrink-0 overflow-hidden">
                          {m.avatar_url ? (
                            <img src={m.avatar_url} alt="" className="w-full h-full object-cover" />
                          ) : (
                            m.full_name.substring(0, 2).toUpperCase()
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-slate-800 dark:text-slate-200 truncate" title={m.full_name}>
                            {m.full_name} {m.id === currentUser?.id && '(You)'}
                          </div>
                          <div className="text-xs text-slate-500 dark:text-slate-400 truncate" title={m.email}>{m.email}</div>
                        </div>
                      </div>
                    </td>

                    {/* Role */}
                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-400">
                        {m.role.name}
                      </span>
                    </td>

                    {/* Department */}
                    <td className="px-4 py-3.5">
                      {m.role.department_name ? (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                          {m.role.department_name}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 dark:text-slate-550 px-2.5 py-1">
                          None
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3.5">
                      {m.is_active ? (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-400">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400">
                          Inactive
                        </span>
                      )}
                    </td>

                    {/* Joined */}
                    <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {formatDate(m.created_at)}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3.5">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          title="Change Role"
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => setEditingUserId(m.id)}
                          className="p-2 text-slate-400 dark:text-slate-500 hover:text-amber-600 dark:hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/40 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400 dark:disabled:hover:text-slate-500 disabled:cursor-not-allowed"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          title={m.is_active ? 'Deactivate' : 'Activate'}
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => setDeactivatingUserId(m.id)}
                          className={`p-2 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed text-slate-400 dark:text-slate-500 ${
                            m.is_active
                              ? 'hover:text-indigo-650 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40'
                              : 'hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40'
                          }`}
                        >
                          {m.is_active ? <UserMinus className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                        </button>
                        <button
                          title="Remove Member"
                          disabled={m.id === currentUser?.id || m.role.is_admin}
                          onClick={() => setDeletingUserId(m.id)}
                          className="p-2 text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400 dark:disabled:hover:text-slate-500 disabled:cursor-not-allowed"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer count */}
        {!loadingMembers && filteredMembers.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Showing {filteredMembers.length} of {members.length} member{members.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </div>

      {/* Invite Modal */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Invite Member</h2>
              <button
                onClick={() => setIsInviteModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded-lg p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleInvite} className="px-6 py-5 space-y-5">
              {inviteStatus && (
                <div className={`flex items-start gap-2 p-3 rounded-lg text-sm border ${
                  inviteStatus.type === 'success'
                    ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50'
                    : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50'
                }`}>
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span className="text-sm">{inviteStatus.msg}</span>
                </div>
              )}
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Full Name</label>
                <input
                  required
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 transition-all"
                />
              </div>
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Email Address</label>
                <input
                  required
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 transition-all"
                />
              </div>
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Role</label>
                <div className="relative">
                  <select
                    required
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="peer appearance-none w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                  >
                    <option value="">Select a role...</option>
                    {roles?.map((r: RoleResponse) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
                </div>
              </div>
              <button
                type="submit"
                className="w-full bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors shadow-sm"
              >
                Send Invite
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deletingUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
            <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Remove Member</h2>
            </div>
            <div className="px-6 py-5">
              <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed font-normal">
                Are you sure you want to permanently remove{' '}
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {members?.find((m: UserResponse) => m.id === deletingUserId)?.full_name}
                </span>
                ? This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3 px-6 pb-6">
              <button
                onClick={() => setDeletingUserId(null)}
                className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deletingUserId)}
                disabled={deleteMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors disabled:opacity-70"
              >
                {deleteMutation.isPending ? (
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deactivate/Activate Confirmation */}
      {deactivatingUserId && (() => {
        const target = members?.find((m: UserResponse) => m.id === deactivatingUserId);
        const newStatus = !target?.is_active;
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
              <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800">
                <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
                  {newStatus ? 'Activate' : 'Deactivate'} Member
                </h2>
              </div>
              <div className="px-6 py-5">
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed font-normal">
                  Are you sure you want to {newStatus ? 'activate' : 'deactivate'}{' '}
                  <span className="font-semibold text-slate-800 dark:text-slate-200">{target?.full_name}</span>?
                </p>
              </div>
              <div className="flex gap-3 px-6 pb-6">
                <button
                  onClick={() => setDeactivatingUserId(null)}
                  className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => updateMutation.mutate({ id: deactivatingUserId, data: { is_active: newStatus } })}
                  disabled={updateMutation.isPending}
                  className="flex-1 flex items-center justify-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors disabled:opacity-70"
                >
                  {updateMutation.isPending ? (
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                  ) : (
                    'Confirm'
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Departments Section */}
        <div className="flex items-center justify-between border-slate-200 dark:border-slate-800 dark:bg-slate-950/20">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              Departments
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Manage departments in your organisation</p>
          </div>
          <button
            onClick={() => {
              setDeptModalType('create');
              setDeptNameInput('');
              setIsDeptModalOpen(true);
            }}
            className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            New Department
          </button>
        </div>
        
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden mt-8">

        {loadingDepartments ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 rounded-full border-4 border-indigo-200 dark:border-indigo-950 border-t-indigo-700 dark:border-t-indigo-500 animate-spin"></div>
          </div>
        ) : departments.length === 0 ? (
          <div className="text-center text-slate-400 dark:text-slate-500 py-16">
            <div className="flex flex-col items-center gap-3">
              <Building2 className="w-12 h-12 text-slate-200 dark:text-slate-800" />
              <p className="font-medium text-slate-500 dark:text-slate-400">No departments created yet</p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800">
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Department Name</th>
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Number of Employees</th>
                  <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">Created At</th>
                  <th className="px-4 py-3.5 text-right font-semibold text-slate-600 dark:text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {departments.map((dept) => {
                  const employeeCount = members.filter((m: UserResponse) => m.role?.department_id === dept.id).length;
                  return (
                    <tr
                      key={dept.id}
                      className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Name */}
                      <td className="px-4 py-3.5 font-medium text-slate-800 dark:text-slate-200">
                        {dept.name}
                      </td>

                      {/* Number of Employees */}
                      <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-400">
                          {employeeCount} {employeeCount === 1 ? 'employee' : 'employees'}
                        </span>
                      </td>

                      {/* Created At */}
                      <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {formatDate(dept.created_at)}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => {
                              setDeptModalType('edit');
                              setEditingDeptId(dept.id);
                              setDeptNameInput(dept.name);
                              setIsDeptModalOpen(true);
                            }}
                            title="Edit Department"
                            className="p-2 text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 rounded-lg transition-colors"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeletingDeptId(dept.id)}
                            title="Delete Department"
                            className="p-2 text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!loadingDepartments && departments.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Showing {departments.length} of {departments.length} department{departments.length !== 1 ? 's' : ''}
            </p>
          </div>
        )}
      </div>

      {/* Create/Edit Department Modal */}
      {isDeptModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
                {deptModalType === 'create' ? 'Create Department' : 'Edit Department'}
              </h2>
              <button
                onClick={() => setIsDeptModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-350 transition-colors rounded-lg p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (deptModalType === 'create') {
                  createDeptMutation.mutate({ name: deptNameInput });
                } else if (editingDeptId) {
                  updateDeptMutation.mutate({ id: editingDeptId, data: { name: deptNameInput } });
                }
              }}
              className="p-6 flex flex-col gap-4"
            >
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Department Name</label>
                <input
                  required
                  autoFocus
                  value={deptNameInput}
                  onChange={(e) => setDeptNameInput(e.target.value)}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={createDeptMutation.isPending || updateDeptMutation.isPending}
                className="mt-2 w-full bg-indigo-700 dark:bg-indigo-500 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50"
              >
                {createDeptMutation.isPending || updateDeptMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Delete Department Modal */}
      {deletingDeptId && (() => {
        const dept = departments.find((d) => d.id === deletingDeptId);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
              <h3 className="text-lg font-semibold mb-2 text-slate-800 dark:text-slate-100">Delete Department</h3>
              <p className="text-slate-500 dark:text-slate-400 mb-6 leading-relaxed text-sm">
                Are you sure you want to delete the department{' '}
                <span className="font-semibold text-slate-800 dark:text-slate-200">{dept?.name}</span>? Roles
                assigned to this department will remain but will be unassociated from it. This action cannot be undone.
              </p>
              <div className="flex gap-3 w-full">
                <button
                  onClick={() => setDeletingDeptId(null)}
                  className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-350 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteDeptMutation.mutate(deletingDeptId)}
                  disabled={deleteDeptMutation.isPending}
                  className="flex-1 py-2 rounded-lg bg-red-600 dark:bg-red-500 hover:bg-red-700 dark:hover:bg-red-400 text-white font-medium transition-colors disabled:opacity-50"
                >
                  {deleteDeptMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Change Role Modal */}
      {editingUserId && targetMember && (() => {
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Change Role & Department</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5 truncate max-w-xs">{targetMember.full_name}</p>
                </div>
                <button
                  onClick={() => setEditingUserId(null)}
                  className="text-slate-400 hover:text-slate-655 dark:text-slate-350 transition-colors rounded-lg p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="px-6 py-5 space-y-5">
                {/* Role Select */}
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Select Role</label>
                  <div className="relative">
                    <select
                      value={modalRoleId}
                      onChange={(e) => {
                        const newRoleId = e.target.value;
                        setModalRoleId(newRoleId);
                        const r = roles.find((role: RoleResponse) => role.id === newRoleId);
                        setModalDeptId(r?.department_id || '');
                      }}
                      className="peer appearance-none w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      {roles?.map((r: RoleResponse) => (
                        <option key={r.id} value={r.id}>{r.name}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
                  </div>
                </div>

                {/* Department Select */}
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Select Department</label>
                  <div className="relative">
                    <select
                      value={modalDeptId}
                      onChange={(e) => setModalDeptId(e.target.value)}
                      className="peer appearance-none w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      <option value="">None (Unassigned)</option>
                      {departments?.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none transition-transform duration-200 peer-focus:rotate-180" />
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => setEditingUserId(null)}
                    className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={async () => {
                      const isPending = updateMutation.isPending || updateRoleDeptMutation.isPending;
                      if (isPending) return;

                      try {
                        // 1. If role changed, update user's role
                        if (modalRoleId !== targetMember.role_id) {
                          await updateMutation.mutateAsync({ id: targetMember.id, data: { role_id: modalRoleId } });
                        }

                        // 2. Update the role's department
                        const roleToUpdate = roles.find((r: RoleResponse) => r.id === modalRoleId);
                        const newDeptId = modalDeptId || null;
                        if (roleToUpdate && roleToUpdate.department_id !== newDeptId) {
                          await updateRoleDeptMutation.mutateAsync({
                            id: modalRoleId,
                            data: {
                              name: roleToUpdate.name,
                              parent_role_id: roleToUpdate.parent_role_id,
                              department_id: newDeptId,
                            },
                          });
                        }

                        setEditingUserId(null);
                        handleSuccess('Member role and department updated successfully');
                      } catch (err: any) {
                        alert(err?.response?.data?.detail || 'Failed to update member role or department');
                      }
                    }}
                    disabled={updateMutation.isPending || updateRoleDeptMutation.isPending}
                    className="flex-1 flex items-center justify-center bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white font-semibold rounded-xl px-4 py-2.5 transition-colors disabled:opacity-70"
                  >
                    {updateMutation.isPending || updateRoleDeptMutation.isPending ? (
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
