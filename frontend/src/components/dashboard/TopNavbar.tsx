import React, { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  LogOut,
  UserCheck,
  FileText,
  Layers,
  Briefcase,
  Building2,
  Award,
  AlertTriangle,
  Database,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { logout } from "../../services/authService";
import ThemeToggle from "../shared/ThemeToggle";
import { useNotificationStore } from "../../store/notificationStore";

const TopNavbar: React.FC = () => {
  const { user, logout: clearAuth } = useAuthStore();
  const { notifications, unreadCount, markAllAsRead } = useNotificationStore();
  const location = useLocation();
  const navigate = useNavigate();

  const [showNotifications, setShowNotifications] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  // Close notifications on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        notifRef.current &&
        !notifRef.current.contains(event.target as Node)
      ) {
        setShowNotifications(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      console.error("Logout failed:", e);
    } finally {
      clearAuth();
      navigate("/login");
    }
  };

  const getPageTitle = () => {
    const path = location.pathname;
    if (path === "/dashboard") return "Dashboard";
    if (path === "/dashboard/team") return "Team Management";
    if (path === "/dashboard/roles") return "Roles and Permissions";
    if (path === "/dashboard/settings") return "Organisation Settings";
    if (path === "/dashboard/chat") return "Chat";
    if (path === "/dashboard/history") return "Chat History";
    if (path === "/dashboard/profile") return "Profile Settings";
    return "Dashboard";
  };

  const initials =
    user?.full_name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .substring(0, 2)
      .toUpperCase() || "U";

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center">
        <h1 className="text-xl font-semibold text-slate-800 dark:text-slate-100">
          {getPageTitle()}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-500 dark:text-slate-400 hidden md:block font-medium">
          {user?.tenant_name || "Organisation"}
        </span>

        <ThemeToggle />

        <div className="relative" ref={notifRef}>
          <button
            onClick={() => {
              const nextShow = !showNotifications;
              setShowNotifications(nextShow);
              if (nextShow) {
                markAllAsRead();
              }
            }}
            className="p-2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-full transition-colors relative"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white ring-2 ring-white dark:ring-slate-900">
                {unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl w-80 sm:w-96 z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                <span className="font-semibold text-slate-800 dark:text-slate-100 text-sm">
                  Notifications
                </span>
                {unreadCount > 0 && (
                  <span className="text-xs bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded-full font-medium">
                    {unreadCount} new
                  </span>
                )}
              </div>
              <div className="max-h-96 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                    <Bell className="w-8 h-8 text-slate-300 dark:text-slate-700 mb-2" />
                    <span className="text-slate-400 dark:text-slate-500 text-sm">
                      All caught up! No notifications.
                    </span>
                  </div>
                ) : (
                  notifications.map((notif) => {
                    const getNotificationIcon = (type: string) => {
                      const baseClass = "w-4 h-4";
                      switch (type) {
                        case "role_assigned":
                          return (
                            <UserCheck
                              className={`${baseClass} text-emerald-500`}
                            />
                          );
                        case "document_access_direct":
                          return (
                            <FileText
                              className={`${baseClass} text-blue-500`}
                            />
                          );
                        case "document_access_inherited_hierarchy":
                          return (
                            <Layers
                              className={`${baseClass} text-violet-500`}
                            />
                          );
                        case "document_access_inherited_department":
                          return (
                            <Briefcase
                              className={`${baseClass} text-amber-500`}
                            />
                          );
                        case "department_added":
                          return (
                            <Building2
                              className={`${baseClass} text-pink-500`}
                            />
                          );
                        case "evaluation_completed":
                          return (
                            <Award className={`${baseClass} text-indigo-500`} />
                          );
                        case "budget_exceeded":
                          return (
                            <AlertTriangle
                              className={`${baseClass} text-rose-500`}
                            />
                          );
                        case "database_access_direct":
                          return (
                            <Database
                              className={`${baseClass} text-indigo-500`}
                            />
                          );
                        case "database_access_inherited_hierarchy":
                          return (
                            <Layers
                              className={`${baseClass} text-violet-500`}
                            />
                          );
                        case "database_access_inherited_department":
                          return (
                            <Briefcase
                              className={`${baseClass} text-emerald-500`}
                            />
                          );
                        default:
                          return (
                            <Bell className={`${baseClass} text-slate-500`} />
                          );
                      }
                    };

                    const formatRelativeTime = (dateString: string) => {
                      const date = new Date(dateString);
                      const now = new Date();
                      const diffMs = now.getTime() - date.getTime();
                      const diffSec = Math.floor(diffMs / 1000);
                      const diffMin = Math.floor(diffSec / 60);
                      const diffHr = Math.floor(diffMin / 60);
                      const diffDays = Math.floor(diffHr / 24);

                      if (diffSec < 60) return "just now";
                      if (diffMin < 60) return `${diffMin}m ago`;
                      if (diffHr < 24) return `${diffHr}h ago`;
                      return `${diffDays}d ago`;
                    };

                    return (
                      <div
                        key={notif.id}
                        onClick={() => {
                          if (
                            notif.type === "evaluation_completed" &&
                            notif.related_evaluation_id
                          ) {
                            navigate(
                              `/dashboard/evaluations/${notif.related_evaluation_id}`,
                            );
                            setShowNotifications(false);
                          }
                        }}
                        className={`px-4 py-3 flex gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer ${!notif.is_read ? "bg-indigo-50/20 dark:bg-indigo-950/5" : ""}`}
                      >
                        <div className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-lg bg-slate-50 dark:bg-slate-800/80 flex items-center justify-center">
                          {getNotificationIcon(notif.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-slate-700 dark:text-slate-300 leading-normal break-words font-sans">
                            {notif.message}
                          </p>
                          <span className="text-[11px] text-slate-400 dark:text-slate-500 mt-1 block font-sans">
                            {formatRelativeTime(notif.created_at)}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 border-l border-slate-200 dark:border-slate-800 pl-4">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 font-semibold text-sm">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt="Avatar"
                className="w-full h-full rounded-full object-cover"
              />
            ) : (
              initials
            )}
          </div>
          <span className="text-sm font-medium text-slate-800 dark:text-slate-100 hidden sm:block">
            {user?.full_name}
          </span>
          <button
            onClick={handleLogout}
            className="p-1.5 ml-1 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 rounded-lg transition-colors"
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
