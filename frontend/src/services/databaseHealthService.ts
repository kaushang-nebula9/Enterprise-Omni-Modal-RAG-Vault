import api from "./api";

export interface DatabaseStatusResponse {
  connection_id: string;
  name: string;
  db_type: string;
  host: string;
  database_name: string;
  status: "active" | "unreachable" | "degraded";
  last_successful_query_at: string | null;
  schema_last_introspected_at: string | null;
}

export interface QueryMetricSummary {
  total: number;
  last_7_days: number;
  last_30_days: number;
}

export interface QuerySuccessRate {
  success_count: number;
  failed_count: number;
  success_rate_percentage: number;
}

export interface QueryVolumeDay {
  date: string;
  count: number;
}

export interface ConnectionAnalyticsBreakdown {
  connection_id: string;
  name: string;
  total_queries: number;
  success_count: number;
  failed_count: number;
  success_rate_percentage: number;
}

export interface DatabaseAnalyticsResponse {
  metrics: QueryMetricSummary;
  success_rate: QuerySuccessRate;
  failure_reasons: Record<string, number>;
  query_volume: QueryVolumeDay[];
  connections: ConnectionAnalyticsBreakdown[];
}

export interface QueryHistoryItem {
  timestamp: string;
  user_email: string;
  user_name: string;
  natural_language_query: string;
  generated_sql: string | null;
  execution_time_ms: number;
  status: "success" | "failed";
  error_message: string | null;
}

export interface PaginatedQueryHistoryResponse {
  items: QueryHistoryItem[];
  total: number;
  page: number;
  pages: number;
  has_more: boolean;
}

export interface ColumnSchema {
  name: string;
  type: string;
}

export interface ForeignKeySchema {
  constrained_columns: string[];
  referred_table: string;
  referred_columns: string[];
}

export interface TableSchema {
  table_name: string;
  columns: ColumnSchema[];
  primary_key?: string[];
  foreign_keys?: ForeignKeySchema[];
}

export const databaseHealthService = {
  getStatus: async (): Promise<DatabaseStatusResponse[]> => {
    const response = await api.get("/api/v1/database-health/status");
    return response.data;
  },

  getAnalytics: async (): Promise<DatabaseAnalyticsResponse> => {
    const response = await api.get("/api/v1/database-health/analytics");
    return response.data;
  },

  getConnectionQueries: async (
    connectionId: string,
    page: number = 1,
    limit: number = 50,
  ): Promise<PaginatedQueryHistoryResponse> => {
    const response = await api.get(
      `/api/v1/database-health/connections/${connectionId}/queries`,
      { params: { page, limit } },
    );
    return response.data;
  },

  getConnectionSchema: async (connectionId: string): Promise<TableSchema[]> => {
    const response = await api.get(
      `/api/v1/database-health/connections/${connectionId}/schema`,
    );
    return response.data;
  },

  refreshConnectionSchema: async (
    connectionId: string,
  ): Promise<{ status: string; message: string }> => {
    const response = await api.post(
      `/api/v1/database-health/connections/${connectionId}/refresh-schema`,
    );
    return response.data;
  },
};
export default databaseHealthService;
