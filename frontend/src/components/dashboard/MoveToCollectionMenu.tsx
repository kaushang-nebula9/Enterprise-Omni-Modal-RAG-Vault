import React, { useState, useEffect, useRef } from "react";
import { Folder, ChevronRight, Check, X, Loader2 } from "lucide-react";
import type { CollectionResponse } from "../../types/document";

interface MoveToCollectionMenuProps {
  documentId: string;
  currentCollectionId: string | null;
  collections: CollectionResponse[];
  onMove: (documentId: string, collectionId: string | null) => Promise<void>;
}

export const MoveToCollectionMenu: React.FC<MoveToCollectionMenuProps> = ({
  documentId,
  currentCollectionId,
  collections,
  onMove,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isSubOpen, setIsSubOpen] = useState(false);
  const [isMoving, setIsMoving] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setIsSubOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleMoveAction = async (collectionId: string | null) => {
    if (isMoving) return;
    setIsMoving(true);
    try {
      await onMove(documentId, collectionId);
      setIsOpen(false);
      setIsSubOpen(false);
    } catch (err) {
      // Error handled by parent hook
    } finally {
      setIsMoving(false);
    }
  };

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      {/* Trigger Button */}
      <button
        type="button"
        title="Move to collection"
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 w-fit text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 rounded-lg transition-colors cursor-pointer"
      >
        <Folder className="w-4 h-4" />
      </button>

      {/* Parent Menu Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-1 w-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-50 py-1">
          {/* Loading overlay */}
          {isMoving && (
            <div className="absolute inset-0 bg-white/60 dark:bg-slate-900/60 flex items-center justify-center rounded-xl z-[60]">
              <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
            </div>
          )}

          {/* Submenu Wrapper */}
          <div className="relative group/sub">
            <button
              type="button"
              onClick={() => setIsSubOpen(!isSubOpen)}
              className="w-full flex items-center justify-between px-3.5 py-2 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors gap-2 cursor-pointer outline-none"
            >
              <span className="flex items-center gap-2 w-fit">
                <Folder className="w-3.5 h-3.5 text-slate-450 shrink-0" />
                Move to Collection
              </span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            </button>

            {/* Submenu Item list: floats to left of parent dropdown */}
            <div
              className={`absolute right-full top-0 mr-1.5 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-50 py-1 transition-all ${
                isSubOpen ? "block" : "hidden group-hover/sub:block"
              }`}
            >
              {/* Remove from Collection Option (if currently in a collection) */}
              {currentCollectionId !== null && (
                <>
                  <button
                    type="button"
                    onClick={() => handleMoveAction(null)}
                    disabled={isMoving}
                    className="w-full flex items-center gap-2 px-3.5 py-2 text-left text-xs text-red-650 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5 shrink-0" />
                    <span>Remove from Collection</span>
                  </button>
                  <div className="border-b border-slate-100 dark:border-slate-800 my-1" />
                </>
              )}

              {/* Collections List */}
              <div className="max-h-48 overflow-y-auto space-y-0.5">
                {collections.length === 0 ? (
                  <div className="px-3.5 py-2 text-left text-xs text-slate-400 dark:text-slate-500 italic">
                    No collections created yet
                  </div>
                ) : (
                  collections.map((col) => {
                    const isCurrent = currentCollectionId === col.id;
                    return (
                      <button
                        key={col.id}
                        type="button"
                        onClick={() => {
                          if (!isCurrent) handleMoveAction(col.id);
                        }}
                        disabled={isMoving}
                        className={`w-full flex items-center justify-between px-3.5 py-2 text-left text-xs transition-colors truncate gap-2 ${
                          isCurrent
                            ? "text-indigo-600 dark:text-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/10 font-medium cursor-default"
                            : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                        }`}
                      >
                        <span className="truncate">{col.name}</span>
                        {isCurrent && (
                          <Check className="w-3.5 h-3.5 shrink-0 text-indigo-500" />
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
