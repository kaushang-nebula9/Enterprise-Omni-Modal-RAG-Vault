import React, { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Search, MessageSquare, Calendar, ChevronDown, X } from "lucide-react";
import { chatService } from "../../services/chatService";
import type { ChatSearchItem } from "../../types/chat";

const HighlightText: React.FC<{ text: string; search: string; caseSensitive?: boolean }> = ({ text, search, caseSensitive }) => {
  if (!search || !search.trim()) return <>{text}</>;
  const escapedSearch = search.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
  const regex = new RegExp(`(${escapedSearch})`, caseSensitive ? "g" : "gi");
  const parts = text?.split(regex);
  return (
    <>
      {parts?.map((part, index) => {
        const isMatch = caseSensitive 
          ? part === search
          : part.toLowerCase() === search.toLowerCase();
        return isMatch ? (
          <mark
            key={index}
            className="bg-indigo-200 dark:bg-indigo-800 text-slate-900 dark:text-slate-100 rounded-sm px-0.5 font-medium"
          >
            {part}
          </mark>
        ) : (
          part
        );
      })}
    </>
  );
};

export const SearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const urlQuery = searchParams.get("q") || "";
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";
  const matchIn = searchParams.get("match_in") || "all";
  const sort = searchParams.get("sort") || "recent";
  const caseSensitive = searchParams.get("case_sensitive") === "true";

  const [inputValue, setInputValue] = useState(urlQuery);
  const [results, setResults] = useState<ChatSearchItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Recent searches state
  const [isFocused, setIsFocused] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  // Sort dropdown states & refs
  const [isSortDropdownOpen, setIsSortDropdownOpen] = useState(false);
  const sortDropdownRef = useRef<HTMLDivElement>(null);

  // Match in dropdown states & refs
  const [isMatchInDropdownOpen, setIsMatchInDropdownOpen] = useState(false);
  const matchInDropdownRef = useRef<HTMLDivElement>(null);

  // Focus the input on mount
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Handle click outside of sort and match_in dropdowns to close them
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        sortDropdownRef.current &&
        !sortDropdownRef.current.contains(event.target as Node)
      ) {
        setIsSortDropdownOpen(false);
      }
      if (
        matchInDropdownRef.current &&
        !matchInDropdownRef.current.contains(event.target as Node)
      ) {
        setIsMatchInDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Debounce the input state to the URL search parameter
  useEffect(() => {
    const handler = setTimeout(() => {
      const trimmed = inputValue.trim();
      if (trimmed !== urlQuery) {
        const nextParams = new URLSearchParams(searchParams);
        if (trimmed) {
          nextParams.set("q", trimmed);
        } else {
          nextParams.delete("q");
        }
        nextParams.delete("offset");
        setSearchParams(nextParams);
      }
    }, 300);
    return () => clearTimeout(handler);
  }, [inputValue, urlQuery, searchParams, setSearchParams]);

  // Synchronize input value with URL when navigating back/forward
  useEffect(() => {
    setInputValue(urlQuery);
  }, [urlQuery]);

  const saveRecentSearch = (term: string) => {
    if (!term.trim()) return;
    try {
      const saved = localStorage.getItem("omnivault_recent_searches");
      let searches: string[] = saved ? JSON.parse(saved) : [];
      searches = [term, ...searches.filter((t) => t !== term)];
      searches = searches.slice(0, 5);
      localStorage.setItem("omnivault_recent_searches", JSON.stringify(searches));
    } catch (e) {
      console.error("Failed to save recent search:", e);
    }
  };

  // Perform search when the URL query parameters change
  useEffect(() => {
    if (!urlQuery.trim()) {
      setResults([]);
      setTotalCount(0);
      setHasMore(false);
      return;
    }

    saveRecentSearch(urlQuery);

    const performSearch = async () => {
      setIsLoading(true);
      try {
        const response = await chatService.searchConversations(
          urlQuery,
          0,
          dateFrom || undefined,
          dateTo || undefined,
          matchIn,
          sort,
          caseSensitive
        );
        setResults(response.results);
        setTotalCount(response.total_count);
        setHasMore(response.has_more);
        setOffset(0);
      } catch (error) {
        console.error("Error searching chats:", error);
      } finally {
        setIsLoading(false);
      }
    };

    performSearch();
  }, [urlQuery, dateFrom, dateTo, matchIn, sort, caseSensitive]);

  const handleLoadMore = async () => {
    if (isLoading || !hasMore) return;
    const nextOffset = offset + 10;
    setIsLoading(true);
    try {
      const response = await chatService.searchConversations(
        urlQuery,
        nextOffset,
        dateFrom || undefined,
        dateTo || undefined,
        matchIn,
        sort,
        caseSensitive
      );
      setResults((prev) => [...prev, ...response.results]);
      setOffset(nextOffset);
      setHasMore(response.has_more);
    } catch (error) {
      console.error("Load more failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const updateFilters = (newFilters: {
    date_from?: string;
    date_to?: string;
    match_in?: string;
    sort?: string;
  }) => {
    const nextParams = new URLSearchParams(searchParams);
    
    if (newFilters.date_from !== undefined) {
      if (newFilters.date_from) {
        nextParams.set("date_from", newFilters.date_from);
      } else {
        nextParams.delete("date_from");
      }
    }
    
    if (newFilters.date_to !== undefined) {
      if (newFilters.date_to) {
        nextParams.set("date_to", newFilters.date_to);
      } else {
        nextParams.delete("date_to");
      }
    }
    
    if (newFilters.match_in !== undefined) {
      if (newFilters.match_in && newFilters.match_in !== "all") {
        nextParams.set("match_in", newFilters.match_in);
      } else {
        nextParams.delete("match_in");
      }
    }
    
    if (newFilters.sort !== undefined) {
      if (newFilters.sort && newFilters.sort !== "recent") {
        nextParams.set("sort", newFilters.sort);
      } else {
        nextParams.delete("sort");
      }
    }

    nextParams.delete("offset");
    setSearchParams(nextParams);
  };

  const clearFilters = () => {
    const nextParams = new URLSearchParams();
    if (urlQuery) {
      nextParams.set("q", urlQuery);
    }
    setSearchParams(nextParams);
  };

  const handleFocus = () => {
    setIsFocused(true);
    try {
      const saved = localStorage.getItem("omnivault_recent_searches");
      if (saved) {
        setRecentSearches(JSON.parse(saved));
      }
    } catch (e) {
      console.error("Failed to load recent searches:", e);
    }
  };

  const handleBlur = () => {
    setTimeout(() => {
      setIsFocused(false);
    }, 200);
  };

  const removeRecentSearch = (term: string) => {
    try {
      const saved = localStorage.getItem("omnivault_recent_searches");
      if (saved) {
        let searches: string[] = JSON.parse(saved);
        searches = searches.filter((t) => t !== term);
        localStorage.setItem("omnivault_recent_searches", JSON.stringify(searches));
        setRecentSearches(searches);
      }
    } catch (e) {
      console.error("Failed to remove recent search:", e);
    }
  };

  const toggleCaseSensitive = () => {
    const nextParams = new URLSearchParams(searchParams);
    if (!caseSensitive) {
      nextParams.set("case_sensitive", "true");
    } else {
      nextParams.delete("case_sensitive");
    }
    nextParams.delete("offset");
    setSearchParams(nextParams);
  };

  const formatConversationDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch (e) {
      return dateStr;
    }
  };

  const isFilterModified = !!(dateFrom || dateTo || matchIn !== "all" || sort !== "recent" || caseSensitive);

  return (
    <div className="flex flex-col -m-6 h-[calc(100vh-4rem)] bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 font-inter relative">
      <header className="py-4 px-6 z-10 flex flex-col gap-3 shrink-0">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 w-full">
          {/* Search Bar + Back Button */}
          <div className="flex items-center gap-3 flex-1 min-w-[200px]">
            <button
              onClick={() => navigate(-1)}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors text-slate-600 dark:text-slate-300 shrink-0"
              title="Go back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Type something to search your chats..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onFocus={handleFocus}
                onBlur={handleBlur}
                className="w-full pl-10 pr-12 py-2 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 bg-white dark:bg-slate-900 transition-all"
              />
              <button
                type="button"
                onClick={toggleCaseSensitive}
                className={`absolute right-3 top-1/2 -translate-y-1/2 px-2 py-0.5 rounded text-xs font-bold transition-all select-none border cursor-pointer ${
                  caseSensitive
                    ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                    : "bg-transparent text-slate-400 border-slate-250/60 dark:border-slate-850 hover:text-slate-600 dark:hover:text-slate-350"
                }`}
                title="Match Case"
              >
                Aa
              </button>
              {/* Recent Searches Dropdown */}
              {isFocused && !inputValue.trim() && recentSearches.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg z-20 py-2">
                  <div className="px-4 py-1.5 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider select-none">
                    Recent searches
                  </div>
                  <div className="flex flex-col">
                    {recentSearches.map((term, index) => (
                      <div
                        key={index}
                        className="w-full flex items-center justify-between px-4 py-1 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group/item"
                      >
                        <button
                          onMouseDown={() => {
                            setInputValue(term);
                            setSearchParams({ q: term });
                          }}
                          className="flex-1 text-left text-sm dark:text-slate-400 dark:text-slate-350 hover:text-slate-900 dark:hover:text-slate-100 font-medium truncate py-1"
                        >
                          {term}
                        </button>
                        <button
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            removeRecentSearch(term);
                          }}
                          className="p-1 hover:bg-slate-250 dark:hover:bg-slate-750/70 rounded-md transition-colors text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 shrink-0 cursor-pointer"
                          title="Remove from history"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 mx-1 shrink-0"></div>

          {/* Filters Row */}
          <div className="flex flex-wrap items-center gap-3 shrink-0 text-slate-700 dark:text-slate-300">
            {/* Date range filter */}
            <div className="flex items-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl px-2  dark:hover:bg-slate-800 transition-colors focus-within:ring-1 focus-within:ring-indigo-500 focus-within:bg-white dark:focus-within:bg-slate-900 overflow-hidden shadow-sm">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => updateFilters({ date_from: e.target.value })}
                className="bg-transparent text-sm text-slate-700 dark:text-slate-200 font- py-2 focus:outline-none cursor-pointer w-fit uppercase dark:[color-scheme:dark]"
                title="Start Date"
              />
              <span className="text-slate-400 dark:text-slate-600 font-medium px-1 select-none">
                -
              </span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => updateFilters({ date_to: e.target.value })}
                className="bg-transparent text-sm text-slate-700 dark:text-slate-200 font- py-2 focus:outline-none cursor-pointer w-fit uppercase dark:[color-scheme:dark]"
                title="End Date"
              />
            </div>

            {/* Matched in dropdown */}
            <div className="flex items-center gap-1.5">
              <div className="relative inline-block text-left" ref={matchInDropdownRef}>
                <button
                  onClick={() => setIsMatchInDropdownOpen(!isMatchInDropdownOpen)}
                  type="button"
                  className="inline-flex items-center justify-between gap-2 px-3 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-55 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[125px] cursor-pointer shadow-sm"
                >
                  <span>
                    {matchIn === "all" && "All matches"}
                    {matchIn === "titles" && "Titles only"}
                    {matchIn === "messages" && "Messages only"}
                  </span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                      isMatchInDropdownOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>

                {isMatchInDropdownOpen && (
                  <div className="absolute right-0 mt-1.5 w-40 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1 animate-in fade-in slide-in-from-top-1 duration-100">
                    {[
                      { value: "all", label: "All matches" },
                      { value: "titles", label: "Titles only" },
                      { value: "messages", label: "Messages only" },
                    ].map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          updateFilters({ match_in: option.value });
                          setIsMatchInDropdownOpen(false);
                        }}
                        type="button"
                        className={`w-full text-left px-4 py-2 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                          matchIn === option.value
                            ? "text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15"
                            : "text-slate-800 dark:text-slate-200"
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Sort order dropdown */}
            <div className="flex items-center gap-1.5">
              <div className="relative inline-block text-left" ref={sortDropdownRef}>
                <button
                  onClick={() => setIsSortDropdownOpen(!isSortDropdownOpen)}
                  type="button"
                  className="inline-flex items-center justify-between gap-2 px-3 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-55 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[125px] cursor-pointer shadow-sm"
                >
                  <span>
                    {sort === "recent" && "Most recent"}
                    {sort === "oldest" && "Oldest first"}
                    {sort === "most_matches" && "Most matches"}
                  </span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                      isSortDropdownOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>

                {isSortDropdownOpen && (
                  <div className="absolute right-0 mt-1.5 w-40 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1 animate-in fade-in slide-in-from-top-1 duration-100">
                    {[
                      { value: "recent", label: "Most recent" },
                      { value: "oldest", label: "Oldest first" },
                      { value: "most_matches", label: "Most matches" },
                    ].map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          updateFilters({ sort: option.value });
                          setIsSortDropdownOpen(false);
                        }}
                        type="button"
                        className={`w-full text-left px-4 py-2 text-xs hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                          sort === option.value
                            ? "text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15"
                            : "text-slate-700 dark:text-slate-350"
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Clear filters button */}
            {isFilterModified && (
              <button
                onClick={clearFilters}
                className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 hover:underline transition-all ml-auto"
              >
                Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Result count line */}
        {urlQuery.trim() && !isLoading && results.length > 0 && (
          <div className="text-xs text-slate-500 dark:text-slate-40 0 font-medium w-full max-w-4xl px-12 -mt-1 -mb-1">
            {totalCount} {totalCount === 1 ? "result" : "results"} for "{urlQuery}"
          </div>
        )}
      </header>

      {/* Main Results body */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-6 flex flex-col gap-6 overflow-y-auto">
        {/* Placeholder state */}
        {!urlQuery.trim() && (
          <div className="flex-1 flex flex-col items-center justify-center text-center mb-12">
            <div className="bg-slate-100 dark:bg-slate-900 p-4 rounded-full mb-4 text-slate-400">
              <Search className="w-8 h-8" />
            </div>
            <h2 className="text-lg font-medium text-slate-700 dark:text-slate-300 mb-1">
              Search Past Conversations
            </h2>
            <p className="text-sm text-slate-400 dark:text-slate-500 max-w-sm">
              Type something to search your chats
            </p>
          </div>
        )}

        {/* Search Results */}
        {urlQuery.trim() && (
          <>
            {results.length > 0 ? (
              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-4">
                  {results.map((item) => (
                    <div
                      key={item.conversation_id}
                      onClick={() => navigate(`/dashboard/chat?session=${item.conversation_id}`)}
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 transition-all cursor-pointer flex flex-col gap-3 group"
                    >
                      {/* Card Header: Title & Time */}
                      <div className="flex justify-between items-start gap-4">
                        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                          <HighlightText text={item.conversation_title} search={urlQuery} caseSensitive={caseSensitive} />
                        </h3>
                        <div className="flex flex-col items-end gap-2 shrink-0">
                          <div className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{formatConversationDate(item.conversation_date)}</span>
                          </div>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-100/50 dark:border-indigo-900/30">
                            {item.match_count} {item.match_count === 1 ? "match" : "matches"}
                          </span>
                        </div>
                      </div>

                      {/* Card Body: Matching lines */}
                      {item.matching_lines.length > 0 ? (
                        <div className="flex flex-col gap-2 bg-slate-50 dark:bg-slate-950 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                          {item.matching_lines.map((line, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-2 text-sm text-slate-650 dark:text-slate-400 leading-relaxed py-0.5"
                            >
                              <span className="text-xs text-slate-400 dark:text-slate-500 select-none shrink-0 pt-0.5 font-medium">
                                {line.role === "user" ? "You: " : "AI: "}
                              </span>
                              <div className="border-l-2 border-slate-200 dark:border-slate-800 pl-3 flex-1">
                                <HighlightText text={line.text} search={urlQuery} caseSensitive={caseSensitive} />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-slate-400 dark:text-slate-500 italic">
                          Matched in conversation title
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Load More button */}
                {hasMore && (
                  <div className="flex justify-center mt-4">
                    <button
                      onClick={handleLoadMore}
                      disabled={isLoading}
                      className="text-sm font-medium text-indigo-700 underline dark:text-indigo-400 transition-all flex items-center gap-2 disabled:opacity-50"
                    >
                      {isLoading ? (
                        <>
                          <svg
                            className="animate-spin h-4 w-4 text-slate-500"
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
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
                          Loading more...
                        </>
                      ) : (
                        "Load more"
                      )}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              // Empty results state
              !isLoading && (
                <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
                  <div className="bg-red-50 dark:bg-red-950/20 p-4 rounded-full mb-4 text-red-500 dark:text-red-400">
                    <MessageSquare className="w-8 h-8" />
                  </div>
                  <h2 className="text-lg font-medium text-slate-700 dark:text-slate-300 mb-1">
                    No results found
                  </h2>
                  <p className="text-sm text-slate-400 dark:text-slate-500 max-w-sm">
                    No results found for '<span className="font-semibold text-slate-600 dark:text-slate-400">{urlQuery}</span>'
                  </p>
                </div>
              )
            )}
          </>
        )}

        {/* Global Loading Spinner / Skeleton */}
        {isLoading && results.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center py-20">
            <svg
              className="animate-spin h-10 w-10 text-indigo-500 mb-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
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
            <span className="text-sm text-slate-400 dark:text-slate-500 font-medium">
              Searching your conversations...
            </span>
          </div>
        )}
      </main>
    </div>
  );
};

export default SearchPage;
