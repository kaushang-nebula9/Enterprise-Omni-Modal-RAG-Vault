import { useState, useEffect } from "react";
import {
  getCollections,
  createCollection,
  renameCollection,
  deleteCollection,
  moveDocumentToCollection,
} from "../services/documentService";
import type { CollectionResponse } from "../types/document";

export const useCollections = () => {
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [uncategorizedCount, setUncategorizedCount] = useState(0);
  const [totalDocuments, setTotalDocuments] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCollections = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getCollections();
      setCollections(data.collections);
      setUncategorizedCount(data.uncategorized_count);
      setTotalDocuments(data.total_documents);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to fetch collections",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateCollection = async (name: string, description?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await createCollection({ name, description });
      await fetchCollections();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Failed to create collection";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const handleRenameCollection = async (collectionId: string, name: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await renameCollection(collectionId, name);
      await fetchCollections();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Failed to rename collection";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteCollection = async (collectionId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await deleteCollection(collectionId);
      await fetchCollections();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Failed to delete collection";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const handleMoveDocument = async (
    documentId: string,
    collectionId: string | null,
  ) => {
    setIsLoading(true);
    setError(null);
    try {
      await moveDocumentToCollection(documentId, collectionId);
      await fetchCollections();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Failed to move document";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCollections();
  }, []);

  return {
    collections,
    uncategorizedCount,
    totalDocuments,
    isLoading,
    error,
    fetchCollections,
    handleCreateCollection,
    handleRenameCollection,
    handleDeleteCollection,
    handleMoveDocument,
  };
};
