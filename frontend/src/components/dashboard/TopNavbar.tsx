import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, LogOut } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { logout } from '../../services/authService';

const TopNavbar: React.FC = () => {
  const { user, logout: clearAuth } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  
  const [showNotifications, setShowNotifications] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  // Close notifications on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      console.error('Logout failed:', e);
    } finally {
      clearAuth();
      navigate('/login');
    }
  };

  const getPageTitle = () => {
    const path = location.pathname;
    if (path === '/dashboard') return 'Dashboard';
    if (path === '/dashboard/team') return 'Team Management';
    if (path === '/dashboard/roles') return 'Roles and Permissions';
    if (path === '/dashboard/settings') return 'Organisation Settings';
    if (path === '/dashboard/chat') return 'Chat';
    if (path === '/dashboard/history') return 'Chat History';
    if (path === '/dashboard/profile') return 'Profile Settings';
    return 'Dashboard';
  };

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase() || 'U';

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center">
        <h1 className="text-xl font-semibold text-slate-800">{getPageTitle()}</h1>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-500 hidden md:block">
          {/* Org name would typically come from user's tenant but we might not have it in UserResponse directly. We can show tenant_id prefix or just omit if not easily available. */}
          {/* Wait, we don't have tenant name in UserResponse. We can omit it or show just User's name. We'll show a placeholder or just rely on user role. */}
          Organisation
        </span>

        <div className="relative" ref={notifRef}>
          <button 
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-full transition-colors relative"
          >
            <Bell className="w-5 h-5" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 bg-white border border-slate-200 rounded-lg shadow-lg p-4 w-72 z-50">
              <div className="flex items-center justify-center h-24">
                <span className="text-slate-400">No notifications</span>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 border-l border-slate-200 pl-4">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-semibold text-sm">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="Avatar" className="w-full h-full rounded-full object-cover" />
            ) : (
              initials
            )}
          </div>
          <span className="text-sm font-medium text-slate-800 hidden sm:block">
            {user?.full_name}
          </span>
          <button 
            onClick={handleLogout}
            className="p-1.5 ml-1 text-slate-400 hover:text-red-500 rounded-lg transition-colors"
            title="Log out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopNavbar;
