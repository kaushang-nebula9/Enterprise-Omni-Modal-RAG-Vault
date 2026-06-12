import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMe } from '../../services/authService';
import { useAuthStore } from '../../store/authStore';

interface AuthGuardProps {
  children: React.ReactNode;
}

const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { user, isAuthenticated, isLoading, setUser, setLoading } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;

    const checkAuth = async () => {
      try {
        setLoading(true);
        const currentUser = await getMe();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch (error) {
        if (isMounted) {
          setUser(null);
          // Only navigate to login if we aren't already on an auth path
          const publicPaths = ['/login', '/register', '/forgot-password', '/reset-password', '/accept-invite'];
          const currentPath = window.location.pathname;
          const isPublicPath = publicPaths.some(path => currentPath.startsWith(path));
          if (!isPublicPath) {
            navigate('/login');
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    if (!user) {
      checkAuth();
    } else {
      setLoading(false);
    }

    return () => {
      isMounted = false;
    };
  }, [user, setUser, setLoading, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
          <svg
            className="h-12 w-12 animate-spin text-indigo-700"
            fill="none"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span className="text-sm font-medium text-slate-500 font-sans">Verifying security session...</span>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <>{children}</> : null;
};

export default AuthGuard;
