import React, { useState, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Trash2,
  Pin,
  History,
  Database,
  ScrollText,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { chatService } from "../../services/chatService";
import { listReports } from "../../services/reportService";
import {
  useSessionsStore,
  selectPinnedSessions,
  selectUnpinnedSessions,
} from "../../store/sessionsStore";
import type { SessionResponse } from "../../types/chat";

interface SidebarProps {
  isExpanded: boolean;
  toggleSidebar: () => void;
}

const adminLinks = [
  { name: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { name: "Documents", icon: FileText, path: "/dashboard/documents" },
  { name: "Databases", icon: Database, path: "/dashboard/databases" },
  { name: "Team Management", icon: Users, path: "/dashboard/team" },
  {
    name: "Roles and Permissions",
    icon: ShieldCheck,
    path: "/dashboard/roles",
  },
  {
    name: "Organisation Settings",
    icon: Settings,
    path: "/dashboard/settings",
  },
  { name: "Audit Log", icon: History, path: "/dashboard/audit-log" },
];

const memberLinks = [
  { name: "New Chat", icon: MessageSquare, path: "/dashboard/chat" },
  { name: "Your Documents", icon: FileText, path: "/dashboard/your-documents" },
  { name: "Reports", icon: ScrollText, path: "/dashboard/reports" },
];

const Sidebar: React.FC<SidebarProps> = ({ isExpanded, toggleSidebar }) => {
  const { user } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  // ─── Sessions store ────────────────────────────────────────────────────────
  const {
    sessions,
    setSessions,
    setLoading,
    updateSession,
    removeSession,
    pinnedHasMore,
    pinnedIsLoadingMore,
    pinnedError,
    unpinnedHasMore,
    unpinnedIsLoadingMore,
    unpinnedError,
    setPinnedHasMore,
    setPinnedError,
    setUnpinnedHasMore,
    setUnpinnedError,
    loadMorePinned,
    loadMoreUnpinned,
  } = useSessionsStore();

  const pinnedSessions = selectPinnedSessions(sessions);
  const unpinnedSessions = selectUnpinnedSessions(sessions);

  // ─── React Query fetches (seeds the Zustand store) ──────────────────────────
  const {
    data: initialPinned,
    isLoading: isLoadingPinned,
    isError: isErrorPinned,
    refetch: refetchPinned,
  } = useQuery({
    queryKey: ["chat-sessions", "pinned"],
    queryFn: () =>
      chatService.getSessions({ is_pinned: true, limit: 10, offset: 0 }),
    enabled: !user?.role.is_admin,
  });

  const {
    data: initialUnpinned,
    isLoading: isLoadingUnpinned,
    isError: isErrorUnpinned,
    refetch: refetchUnpinned,
  } = useQuery({
    queryKey: ["chat-sessions", "unpinned"],
    queryFn: () =>
      chatService.getSessions({ is_pinned: false, limit: 10, offset: 0 }),
    enabled: !user?.role.is_admin,
  });

  const { data: reports = [] } = useQuery({
    queryKey: ["reports-list"],
    queryFn: listReports,
    enabled: !user?.role.is_admin,
    refetchInterval: 10000, // Poll every 10s for the badge
  });

  const generatingCount = reports.filter(
    (r) => r.status === "generating",
  ).length;

  // Seed / sync the Zustand store whenever React Query fetches fresh data
  useEffect(() => {
    if (initialPinned !== undefined && initialUnpinned !== undefined) {
      setSessions([...initialPinned, ...initialUnpinned]);
      setPinnedHasMore(initialPinned.length === 10);
      setUnpinnedHasMore(initialUnpinned.length === 10);
      setPinnedError(null);
      setUnpinnedError(null);
    }
  }, [
    initialPinned,
    initialUnpinned,
    setSessions,
    setPinnedHasMore,
    setUnpinnedHasMore,
    setPinnedError,
    setUnpinnedError,
  ]);

  useEffect(() => {
    setLoading(isLoadingPinned || isLoadingUnpinned);
  }, [isLoadingPinned, isLoadingUnpinned, setLoading]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    // Auto-load unpinned chats when scrolled near the bottom (within 50px)
    const isNearBottom =
      target.scrollHeight - target.scrollTop - target.clientHeight < 50;
    if (isNearBottom && isExpanded) {
      loadMoreUnpinned();
    }
  };

  // ─── Delete ───────────────────────────────────────────────────────────────
  const queryClient = useQueryClient();
  const [sessionToDelete, setSessionToDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => chatService.deleteSession(sessionId),
    onSuccess: (_, deletedId) => {
      removeSession(deletedId);
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      setSessionToDelete(null);
      if (location.search.includes(`session=${deletedId}`)) {
        navigate("/dashboard/chat");
      }
    },
  });

  // ─── Pin ──────────────────────────────────────────────────────────────────
  const pinMutation = useMutation({
    mutationFn: (sessionId: string) => chatService.togglePin(sessionId),
    onMutate: (sessionId) => {
      // Optimistic update — flip the flag immediately
      const session = sessions.find((s) => s.id === sessionId);
      if (session) {
        updateSession({ ...session, is_pinned: !session.is_pinned });
      }
      return { session };
    },
    onSuccess: (updated) => {
      // Reconcile with authoritative server state
      updateSession(updated);
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    },
    onError: (_err, _sessionId, context) => {
      // Roll back optimistic update
      if (context?.session) {
        updateSession(context.session);
      }
    },
  });

  // ─── Helpers ──────────────────────────────────────────────────────────────
  const renderLink = (link: {
    name: string;
    icon: React.ElementType;
    path: string;
  }) => {
    const isChat = link.path === "/dashboard/chat";
    const isActive = isChat
      ? location.pathname === link.path && !location.search.includes("session=")
      : location.pathname === link.path;

    const Icon = link.icon;
    const isReports = link.name === "Reports";

    return (
      <NavLink
        key={link.path}
        to={link.path}
        className={`flex items-center rounded-lg transition-colors overflow-hidden ${
          isActive
            ? "bg-indigo-700 dark:bg-indigo-500 text-white"
            : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
        } ${isExpanded ? "px-3 py-2.5" : "justify-center p-2.5"}`}
        title={!isExpanded ? link.name : undefined}
      >
        <div className="relative flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 shrink-0" />
          {isReports && generatingCount > 0 && !isExpanded && (
            <span className="absolute -top-1 -right-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
          )}
        </div>
        {isExpanded && (
          <span className="ml-3 font-medium whitespace-nowrap flex-1 flex justify-between items-center">
            <span>{link.name}</span>
            {isReports && generatingCount > 0 && (
              <span className="inline-flex items-center justify-center text-xs w-4 h-4 font-semibold leading-none text-white bg-indigo-600 dark:bg-indigo-500 rounded-full">
                {generatingCount}
              </span>
            )}
          </span>
        )}
      </NavLink>
    );
  };

  const renderSessionItem = (session: SessionResponse) => {
    const isActive = location.search.includes(`session=${session.id}`);

    return (
      <div
        key={session.id}
        onClick={() => navigate(`/dashboard/chat?session=${session.id}`)}
        className={`group relative flex items-center justify-between rounded-lg transition-colors cursor-pointer overflow-hidden ${
          isActive
            ? "bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 font-medium"
            : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
        } ${isExpanded ? "px-3 py-2" : "justify-center p-2.5"}`}
        title={session.title}
      >
        <div className="flex items-center min-w-0 flex-1">
          {!isExpanded && <MessageSquare className="w-4 h-4 shrink-0" />}
          {isExpanded && (
            <span className="text-sm truncate w-full">{session.title}</span>
          )}
        </div>

        {isExpanded && (
          <div
            className={`absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5 pl-8 pr-2 py-1 bg-gradient-to-l rounded-r-lg transition-all duration-200 opacity-0 group-hover:opacity-100 ${
              isActive
                ? "from-indigo-50 dark:from-indigo-950 from-[60%] to-transparent"
                : "from-white dark:from-slate-900 group-hover:from-slate-100 dark:group-hover:from-slate-800 from-[60%] to-transparent"
            }`}
          >
            {/* Pin button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                pinMutation.mutate(session.id);
              }}
              className={`p-1 rounded transition-all hover:bg-slate-200 dark:hover:bg-slate-700 ${
                session.is_pinned
                  ? "text-indigo-500 dark:text-indigo-400"
                  : "text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400"
              }`}
              title={session.is_pinned ? "Unpin chat" : "Pin chat"}
              disabled={pinMutation.isPending}
            >
              <Pin
                className="w-3.5 h-3.5"
                style={session.is_pinned ? { fill: "currentColor" } : undefined}
              />
            </button>

            {/* Delete button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSessionToDelete({ id: session.id, title: session.title });
              }}
              className="text-slate-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 transition-opacity p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 shrink-0"
              title="Delete chat"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    );
  };

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className={`flex flex-col bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 h-screen shrink-0 ${
        isExpanded ? "w-72" : "w-16"
      }`}
    >
      <div className="flex h-16 items-center justify-center border-b border-slate-200 dark:border-slate-800 shrink-0">
        <span className="font-bold font-sora text-xl tracking-tight whitespace-nowrap overflow-hidden text-slate-800 dark:text-slate-100">
          {isExpanded ? "RAG Vault" : "RV"}
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
              {!isExpanded && (
                <div className="border-t border-slate-200 dark:border-slate-800 my-4 shrink-0" />
              )}

              <div
                className="flex-1 overflow-y-auto space-y-1 custom-scrollbar pr-1"
                onScroll={handleScroll}
              >
                {(isLoadingPinned || isLoadingUnpinned) &&
                sessions.length === 0 ? (
                  isExpanded ? (
                    <div className="px-3 text-slate-400 dark:text-slate-500 text-sm animate-pulse">
                      Loading...
                    </div>
                  ) : null
                ) : (isErrorPinned || isErrorUnpinned) &&
                  sessions.length === 0 ? (
                  isExpanded ? (
                    <div className="px-3 py-2 flex flex-col gap-2 items-start text-sm">
                      <span className="text-red-500 text-xs">
                        Failed to load chats.
                      </span>
                      <button
                        onClick={() => {
                          if (isErrorPinned) refetchPinned();
                          if (isErrorUnpinned) refetchUnpinned();
                        }}
                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-semibold transition-colors"
                      >
                        Retry
                      </button>
                    </div>
                  ) : null
                ) : sessions.length === 0 ? (
                  isExpanded ? (
                    <div className="px-3 text-slate-400 dark:text-slate-500 text-sm italic">
                      No recent chats
                    </div>
                  ) : null
                ) : (
                  <>
                    {/* ── Pinned section ── */}
                    {pinnedSessions.length > 0 && isExpanded && (
                      <div className="mb-4">
                        <p className="px-3 pb-1 text-sm font-semibold text-slate-900 dark:text-slate-400 select-none">
                          Pinned
                        </p>
                        <div className="space-y-1">
                          {pinnedSessions.map(renderSessionItem)}

                          {pinnedIsLoadingMore && (
                            <div className="px-3 py-1 text-xs font-medium text-indigo-600 dark:text-indigo-400">
                              Loading more...
                            </div>
                          )}
                          {pinnedError && (
                            <div className="px-3 py-1 flex flex-col items-start gap-1">
                              <span className="text-xs text-red-500">
                                {pinnedError}
                              </span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  loadMorePinned();
                                }}
                                className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
                              >
                                Retry
                              </button>
                            </div>
                          )}
                          {pinnedHasMore &&
                            !pinnedIsLoadingMore &&
                            !pinnedError && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  loadMorePinned();
                                }}
                                className="w-full text-left px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
                              >
                                Load More...
                              </button>
                            )}
                        </div>
                      </div>
                    )}

                    {/* ── Chat History section ── */}
                    {isExpanded && (
                      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-400 mb-3 px-3 select-none">
                        Chat History
                      </h3>
                    )}

                    {unpinnedSessions.length > 0 && isExpanded && (
                      <div className="space-y-1">
                        {unpinnedSessions.map(renderSessionItem)}

                        {unpinnedIsLoadingMore && (
                          <div className="px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400">
                            Loading more...
                          </div>
                        )}
                        {unpinnedError && (
                          <div className="px-3 py-1 flex flex-col items-start gap-1">
                            <span className="text-xs text-red-500">
                              {unpinnedError}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                loadMoreUnpinned();
                              }}
                              className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
                            >
                              Retry
                            </button>
                          </div>
                        )}
                        {unpinnedHasMore &&
                          !unpinnedIsLoadingMore &&
                          !unpinnedError && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                loadMoreUnpinned();
                              }}
                              className="w-full text-left px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
                            >
                              Load More
                            </button>
                          )}
                      </div>
                    )}

                    {/* When collapsed, render all sessions flat (no grouping headers) */}
                    {!isExpanded &&
                      [...pinnedSessions, ...unpinnedSessions].map(
                        renderSessionItem,
                      )}

                    {!isExpanded &&
                      (unpinnedIsLoadingMore || pinnedIsLoadingMore) && (
                        <div className="flex justify-center py-2 animate-pulse text-indigo-600 dark:text-indigo-400 text-xs">
                          • • •
                        </div>
                      )}
                  </>
                )}
              </div>
            </div>

            <div className="mt-auto pt-4 flex flex-col gap-2 shrink-0">
              {renderLink({
                name: "Profile Settings",
                icon: UserCircle,
                path: "/dashboard/profile",
              })}
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 dark:border-slate-800 p-3 flex justify-center shrink-0">
        <button
          onClick={toggleSidebar}
          className="text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg p-2 w-full flex justify-center transition-colors"
          aria-label={isExpanded ? "Collapse Sidebar" : "Expand Sidebar"}
        >
          {isExpanded ? (
            <ChevronLeft className="w-5 h-5" />
          ) : (
            <ChevronRight className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Delete confirmation modal */}
      {sessionToDelete && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center">
          <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl text-slate-800 dark:text-slate-100">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Delete Chat
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-2">
              Are you sure you want to delete "{sessionToDelete.title}"? This
              action cannot be undone.
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
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
