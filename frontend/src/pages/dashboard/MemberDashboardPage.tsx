import React, { useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { useNavigate } from 'react-router-dom';
import { Send } from 'lucide-react';

const MemberDashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    
    navigate(`/dashboard/chat?q=${encodeURIComponent(query)}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full w-full max-w-4xl mx-auto">
      {/* Welcome Section */}
      <div className="flex flex-col gap-2 pt-4 pb-12 shrink-0">
        <h2 className="font-sora text-2xl font-semibold text-slate-800 dark:text-slate-100">
          Welcome back, {user?.full_name}
        </h2>
        <p className="text-slate-500 dark:text-slate-400">
          What would you like to know today?
        </p>
      </div>

      {/* Chat Input Area */}
      <div className="flex-1 flex flex-col justify-center items-center gap-12 pb-24">
        {!query && (
          <h1 className="text-3xl font-medium text-slate-400 dark:text-slate-500 font-sora transition-opacity duration-500">
            How can I help you today?
          </h1>
        )}
        
        <div className="w-full max-w-2xl px-4 relative group">
          <div className="absolute inset-0 bg-indigo-50 dark:bg-indigo-950/20 rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
          <div className="relative flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-indigo-100 dark:focus-within:ring-indigo-950/50 focus-within:border-indigo-400 dark:focus-within:border-indigo-500 transition-all">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything..."
              className="w-full bg-transparent px-5 py-4 outline-none text-slate-800 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 rounded-2xl text-lg"
              autoFocus
            />
            <button
              onClick={() => handleSend()}
              disabled={!query.trim()}
              className="absolute right-2 p-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400 text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MemberDashboardPage;
