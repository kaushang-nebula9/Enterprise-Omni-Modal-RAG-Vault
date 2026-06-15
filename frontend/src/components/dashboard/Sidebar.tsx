import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  ShieldCheck, 
  Settings, 
  MessageSquare, 
  History, 
  UserCircle,
  ChevronLeft,
  ChevronRight,
  FileText
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

interface SidebarProps {
  isExpanded: boolean;
  toggleSidebar: () => void;
}

const adminLinks = [
  { name: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { name: 'Documents', icon: FileText, path: '/dashboard/documents' },
  { name: 'Team Management', icon: Users, path: '/dashboard/team' },
  { name: 'Roles and Permissions', icon: ShieldCheck, path: '/dashboard/roles' },
  { name: 'Organisation Settings', icon: Settings, path: '/dashboard/settings' },
];

const memberLinks = [
  { name: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { name: 'Chat', icon: MessageSquare, path: '/dashboard/chat' },
  { name: 'Chat History', icon: History, path: '/dashboard/history' },
  { name: 'Profile Settings', icon: UserCircle, path: '/dashboard/profile' },
];

const Sidebar: React.FC<SidebarProps> = ({ isExpanded, toggleSidebar }) => {
  const { user } = useAuthStore();
  const location = useLocation();

  const links = user?.role.is_admin ? adminLinks : memberLinks;

  return (
    <div 
      className={`flex flex-col bg-slate-900 text-white transition-all duration-300 h-screen shrink-0 ${
        isExpanded ? 'w-64' : 'w-16'
      }`}
    >
      <div className="flex h-16 items-center justify-center border-b border-slate-800">
        <span className="font-bold font-sora text-xl tracking-tight whitespace-nowrap overflow-hidden">
          {isExpanded ? 'RAG Vault' : 'RV'}
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 flex flex-col gap-2 px-3">
        {links.map((link) => {
          const isActive = location.pathname === link.path;
          const Icon = link.icon;
          
          return (
            <NavLink
              key={link.path}
              to={link.path}
              className={`flex items-center rounded-lg transition-colors overflow-hidden ${
                isActive
                  ? 'bg-indigo-700 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              } ${isExpanded ? 'px-3 py-2.5' : 'justify-center p-2.5'}`}
              title={!isExpanded ? link.name : undefined}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {isExpanded && (
                <span className="ml-3 font-medium whitespace-nowrap">{link.name}</span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 p-3 flex justify-center">
        <button
          onClick={toggleSidebar}
          className="text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg p-2 w-full flex justify-center transition-colors"
          aria-label={isExpanded ? 'Collapse Sidebar' : 'Expand Sidebar'}
        >
          {isExpanded ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
