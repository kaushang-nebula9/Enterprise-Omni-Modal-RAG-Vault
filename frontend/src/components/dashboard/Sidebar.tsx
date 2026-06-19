import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  LayoutDashboard, 
  Users, 
  ShieldCheck, 
  Settings, 
  MessageSquare, 
  UserCircle,
  ChevronLeft,
  ChevronRight,
  FileText,
  Trash2
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { chatService } from '../../services/chatService';

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
  { name: 'New Chat', icon: MessageSquare, path: '/dashboard/chat' },
  { name: 'Your Documents', icon: FileText, path: '/dashboard/your-documents' },
];

const Sidebar: React.FC<SidebarProps> = ({ isExpanded, toggleSidebar }) => {
  const { user } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: chatService.getSessions,
    enabled: !user?.role.is_admin,
  });

  const queryClient = useQueryClient();
  const [sessionToDelete, setSessionToDelete] = useState<{ id: string; title: string } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => chatService.deleteSession(sessionId),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      setSessionToDelete(null);
      // If the user was viewing the deleted session, clear it from the URL
      if (location.search.includes(`session=${deletedId}`)) {
        navigate('/dashboard/chat');
      }
    },
  });

  const renderLink = (link: { name: string, icon: React.ElementType, path: string }) => {
    // Exact match for the New Chat so it doesn't stay highlighted when viewing an old session
    // Actually, we want it to be highlighted if we are on /dashboard/chat and NO session is in URL.
    const isChat = link.path === '/dashboard/chat';
    const isActive = isChat 
      ? location.pathname === link.path && !location.search.includes('session=')
      : location.pathname === link.path;
      
    const Icon = link.icon;
    
    return (
      <NavLink
        key={link.path}
        to={link.path}
        className={`flex items-center rounded-lg transition-colors overflow-hidden ${
          isActive
            ? 'bg-indigo-700 dark:bg-indigo-500 text-white'
            : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
        } ${isExpanded ? 'px-3 py-2.5' : 'justify-center p-2.5'}`}
        title={!isExpanded ? link.name : undefined}
      >
        <Icon className="w-5 h-5 shrink-0" />
        {isExpanded && (
          <span className="ml-3 font-medium whitespace-nowrap">{link.name}</span>
        )}
      </NavLink>
    );
  };

  return (
    <div 
      className={`flex flex-col bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 h-screen shrink-0 ${
        isExpanded ? 'w-72' : 'w-16'
      }`}
    >
      <div className="flex h-16 items-center justify-center border-b border-slate-200 dark:border-slate-800 shrink-0">
        <span className="font-bold font-sora text-xl tracking-tight whitespace-nowrap overflow-hidden text-slate-800 dark:text-slate-100">
          {isExpanded ? 'RAG Vault' : 'RV'}
        </span>
      </div>

      <div className="flex-1 py-4 flex flex-col px-1 pr-2 overflow-hidden">
        {user?.role.is_admin ? (
          <nav className="flex flex-col gap-2 overflow-y-auto custom-scrollbar pr-1">
            {adminLinks.map(renderLink)}
          </nav>
        ) : (
          <div className="flex flex-col h-full overflow-hidden">
            <nav className="flex flex-col gap-2 shrink-0">
              {memberLinks.map(renderLink)}
            </nav>

            <div className="mt-6 flex-1 flex flex-col overflow-hidden">
              {isExpanded && (
                <h3 className="text-sm font-bold text-slate-400 dark:text-slate-500 tracking-wider mb-3 px-3 shrink-0 select-none">
                  Chat History
                </h3>
              )}
              {!isExpanded && <div className="border-t border-slate-200 dark:border-slate-800 my-4 shrink-0" />}
              
              <div className="flex-1 overflow-y-auto space-y-1 custom-scrollbar pr-1">
                {isLoading ? (
                  isExpanded ? (
                    <div className="px-3 text-slate-400 dark:text-slate-500 text-sm animate-pulse">Loading...</div>
                  ) : null
                ) : sessions && sessions.length > 0 ? (
                  sessions.map((session) => (
                    <div
                      key={session.id}
                      onClick={() => navigate(`/dashboard/chat?session=${session.id}`)}
                      className={`group flex items-center justify-between rounded-lg transition-colors cursor-pointer overflow-hidden ${
                        location.search.includes(`session=${session.id}`) 
                          ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-medium' 
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
                      } ${isExpanded ? 'px-3 py-2' : 'justify-center p-2.5'}`}
                      title={session.title}
                    >
                      <div className="flex items-center min-w-0 flex-1">
                        {!isExpanded && <MessageSquare className="w-4 h-4 shrink-0" />}
                        {isExpanded && (
                          <span className="text-sm truncate">{session.title}</span>
                        )}
                      </div>
                      
                      {isExpanded && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSessionToDelete({ id: session.id, title: session.title });
                          }}
                          className="text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 -mr-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 shrink-0"
                          title="Delete chat"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  isExpanded ? (
                    <div className="px-3 text-slate-400 dark:text-slate-500 text-sm italic">No recent chats</div>
                  ) : null
                )}
              </div>
            </div>

            <div className="mt-auto pt-4 flex flex-col gap-2 shrink-0">
              {renderLink({ name: 'Profile Settings', icon: UserCircle, path: '/dashboard/profile' })}
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 dark:border-slate-800 p-3 flex justify-center shrink-0">
        <button
          onClick={toggleSidebar}
          className="text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg p-2 w-full flex justify-center transition-colors"
          aria-label={isExpanded ? 'Collapse Sidebar' : 'Expand Sidebar'}
        >
          {isExpanded ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
        </button>
      </div>

      {/* Delete confirmation modal */}
      {sessionToDelete && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center">
          <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl text-slate-800 dark:text-slate-100">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Delete Chat</h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-2">
              Are you sure you want to delete "{sessionToDelete.title}"? This action cannot be undone.
            </p>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setSessionToDelete(null)}
                className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(sessionToDelete.id)}
                className="flex-1 flex items-center justify-center px-4 py-2.5 bg-red-500 dark:bg-red-600 hover:bg-red-600 dark:hover:bg-red-500 text-white rounded-xl font-medium transition-colors"
                disabled={deleteMutation.isPending}
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

export default Sidebar;
