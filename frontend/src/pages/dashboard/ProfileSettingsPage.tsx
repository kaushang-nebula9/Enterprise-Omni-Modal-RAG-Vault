import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { updateProfile, setPassword as setPasswordAPI } from '../../services/authService';
import { useAuthStore } from '../../store/authStore';

export const ProfileSettingsPage: React.FC = () => {
  const { user, setUser } = useAuthStore();
  
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [profileStatus, setProfileStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  const profileMutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: (updatedUser) => {
      setUser(updatedUser);
      setProfileStatus({ type: 'success', msg: 'Profile updated successfully' });
      setTimeout(() => setProfileStatus(null), 3000);
    },
    onError: (err: any) => {
      setProfileStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to update profile' });
    }
  });

  const handleProfileUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    profileMutation.mutate({ full_name: fullName });
  };

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordStatus, setPasswordStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

  const passwordMutation = useMutation({
    mutationFn: setPasswordAPI,
    onSuccess: () => {
      if (user) {
        setUser({ ...user, has_password: true });
      }
      setPasswordStatus({ type: 'success', msg: 'Password set successfully' });
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setPasswordStatus(null), 3000);
    },
    onError: (err: any) => {
      setPasswordStatus({ type: 'error', msg: err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || 'Failed to set password' });
    }
  });

  const handleSetPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordStatus({ type: 'error', msg: 'Passwords do not match' });
      return;
    }
    passwordMutation.mutate({ new_password: newPassword, confirm_password: confirmPassword });
  };

  const initials = user?.full_name?.split(' ').map((n) => n[0]).join('').substring(0, 2).toUpperCase() || 'U';

  return (
    <div className="flex flex-col gap-8 w-full max-w-3xl mx-auto h-full pb-12 text-slate-800 dark:text-slate-100">
      <div className="shrink-0">
        <h1 className="text-2xl font-semibold font-sora text-slate-800 dark:text-slate-100">Profile Settings</h1>
      </div>

      <div className="flex flex-col gap-6">
        <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-6 mb-8">
            <div className="w-24 h-24 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 flex items-center justify-center font-bold text-2xl overflow-hidden shrink-0">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                initials
              )}
            </div>
            <div>
              <h2 className="text-xl font-medium text-slate-800 dark:text-slate-100">{user?.full_name}</h2>
              <p className="text-slate-500 dark:text-slate-400">{user?.email}</p>
            </div>
          </div>

          <form onSubmit={handleProfileUpdate} className="flex flex-col gap-4">
            {profileStatus && (
              <div className={`p-3 rounded-lg text-sm border ${
                profileStatus.type === 'success' 
                  ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50' 
                  : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50'
              }`}>
                {profileStatus.msg}
              </div>
            )}
            <div className="space-y-1 max-w-md">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Full Name</label>
              <input required value={fullName} onChange={e=>setFullName(e.target.value)} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
            </div>
            <button type="submit" disabled={profileMutation.isPending || fullName === user?.full_name} className="mt-2 w-fit px-6 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white rounded-lg py-2.5 font-medium transition-colors disabled:opacity-50">
              {profileMutation.isPending ? 'Saving...' : 'Save Profile'}
            </button>
          </form>
        </section>

        {user && !user.has_password && (
          <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-2 font-sora">Set a Password</h2>
            <p className="text-slate-500 dark:text-slate-400 mb-6 text-sm">You signed in with Google. Set a password to also log in with email.</p>
            
            <form onSubmit={handleSetPassword} className="flex flex-col gap-4 max-w-md">
              {passwordStatus && (
                <div className={`p-3 rounded-lg text-sm border ${
                  passwordStatus.type === 'success' 
                    ? 'bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-900/50' 
                    : 'bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-900/50'
                }`}>
                  {passwordStatus.msg}
                </div>
              )}
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">New Password</label>
                <input required type="password" value={newPassword} onChange={e=>setNewPassword(e.target.value)} minLength={8} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Confirm Password</label>
                <input required type="password" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} minLength={8} className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-950/50 focus:border-indigo-500 dark:focus:border-indigo-400 text-slate-800 dark:text-slate-100 outline-none transition-all" />
              </div>
              <button type="submit" disabled={passwordMutation.isPending} className="mt-2 w-fit px-6 bg-indigo-700 dark:bg-indigo-50 text-white rounded-lg py-2.5 font-medium hover:bg-indigo-600 dark:hover:bg-indigo-400 transition-colors disabled:opacity-50">
                {passwordMutation.isPending ? 'Saving...' : 'Set Password'}
              </button>
            </form>
          </section>
        )}
      </div>
    </div>
  );
};
