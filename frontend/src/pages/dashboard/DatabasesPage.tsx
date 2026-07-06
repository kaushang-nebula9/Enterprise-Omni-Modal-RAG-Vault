import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Database, 
  Plus, 
  RefreshCw, 
  Trash2, 
  ShieldCheck, 
  Eye, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Search, 
  Lock, 
  Unlock 
} from 'lucide-react';
import { databaseService } from '../../services/databaseService';
import { roleService } from '../../services/roleService';
import { departmentService } from '../../services/departmentService';

// Format helper
function formatDate(iso: string | null): string {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export const DatabasesPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Queries
  const { data: databases = [], isLoading: isDbsLoading } = useQuery({
    queryKey: ['databases'],
    queryFn: databaseService.getDatabases,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ['roles'],
    queryFn: roleService.getRoles,
  });

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: departmentService.getDepartments,
  });

  // State
  const [search, setSearch] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isAccessModalOpen, setIsAccessModalOpen] = useState(false);
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);

  // Form State
  const [connId, setConnId] = useState<string | null>(null); // null for create
  const [name, setName] = useState('');
  const [engine, setEngine] = useState('postgresql');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(5432);
  const [databaseName, setDatabaseName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [sslMode, setSslMode] = useState('prefer');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Access Modal State
  const [activeDbId, setActiveDbId] = useState<string | null>(null);
  const [activeDbName, setActiveDbName] = useState('');
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [selectedDeptId, setSelectedDeptId] = useState('');
  const [selectedTable, setSelectedTable] = useState(''); // Empty string means "Whole Database"
  const [dbTables, setDbTables] = useState<string[]>([]);

  // Schema Modal State
  const [schemaDbId, setSchemaDbId] = useState<string | null>(null);
  const [schemaDbName, setSchemaDbName] = useState('');

  // Access policies query
  const { data: accessPolicies = [], refetch: refetchAccess } = useQuery({
    queryKey: ['database-access', activeDbId],
    queryFn: () => databaseService.listAccessPolicies(activeDbId!),
    enabled: !!activeDbId,
  });

  // Schema query
  const { data: schemaCache = { tables: [] }, refetch: refetchSchemaCache } = useQuery({
    queryKey: ['database-schema', schemaDbId],
    queryFn: () => databaseService.getDatabaseSchema(schemaDbId!),
    enabled: !!schemaDbId,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: databaseService.createDatabase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] });
      setIsFormOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => databaseService.updateDatabase(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] });
      setIsFormOpen(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: databaseService.deleteDatabase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] });
    },
  });

  const refreshSchemaMutation = useMutation({
    mutationFn: databaseService.refreshSchema,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] });
    },
  });

  const grantAccessMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => databaseService.grantAccess(id, payload),
    onSuccess: () => {
      refetchAccess();
      setSelectedRoleId('');
      setSelectedDeptId('');
      setSelectedTable('');
    },
  });

  const revokeAccessMutation = useMutation({
    mutationFn: ({ id, policyId }: { id: string; policyId: string }) => databaseService.revokeAccess(id, policyId),
    onSuccess: () => {
      refetchAccess();
    },
  });

  // Handlers
  const resetForm = () => {
    setConnId(null);
    setName('');
    setEngine('postgresql');
    setHost('');
    setPort(5432);
    setDatabaseName('');
    setUsername('');
    setPassword('');
    setSslMode('prefer');
    setTestResult(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsFormOpen(true);
  };

  const handleOpenEdit = (dbConn: any) => {
    setConnId(dbConn.id);
    setName(dbConn.name);
    setEngine(dbConn.engine);
    setHost(dbConn.host);
    setPort(dbConn.port);
    setDatabaseName(dbConn.database_name);
    setUsername(dbConn.username);
    setPassword(''); // leave blank unless changing
    setSslMode(dbConn.ssl_mode || 'prefer');
    setTestResult(null);
    setIsFormOpen(true);
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const payload: any = {
        engine,
        host,
        port: Number(port),
        database_name: databaseName,
        username,
        password: password || 'placeholder-ignored', // if editing and password blank, backend tests existing, but we should handle it
        ssl_mode: sslMode,
      };
      
      // If editing and password is empty, we must send a test requesting the existing decrypted password on backend,
      // but since we want to be safe, we'll prompt the user to input password for test, or if it is empty, we warn.
      if (connId && !password) {
        setTestResult({
          success: false,
          message: "Please enter the database password to run a connection test.",
        });
        setIsTesting(false);
        return;
      }

      const res = await databaseService.testConnection(payload);
      setTestResult({ success: true, message: res.message });
    } catch (e: any) {
      setTestResult({
        success: false,
        message: e.response?.data?.detail || "Connection test failed.",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveConnection = () => {
    const payload: any = {
      name,
      engine,
      host,
      port: Number(port),
      database_name: databaseName,
      username,
      ssl_mode: sslMode,
    };
    if (password) {
      payload.password = password;
    }

    if (connId) {
      updateMutation.mutate({ id: connId, data: payload });
    } else {
      if (!password) {
        alert("Password is required for new database connections.");
        return;
      }
      createMutation.mutate(payload as any);
    }
  };

  const handleOpenAccess = async (dbConn: any) => {
    setActiveDbId(dbConn.id);
    setActiveDbName(dbConn.name);
    setSelectedRoleId('');
    setSelectedDeptId('');
    setSelectedTable('');
    
    // Fetch tables for table-scoped grants from schema cache
    try {
      const schema = await databaseService.getDatabaseSchema(dbConn.id);
      const tablesList = schema.tables?.map((t: any) => t.name) || [];
      setDbTables(tablesList);
    } catch (e) {
      setDbTables([]);
    }
    
    setIsAccessModalOpen(true);
  };

  const handleGrantAccess = () => {
    if (!activeDbId) return;
    const payload: any = {
      table_name: selectedTable || null,
    };
    if (selectedRoleId) {
      payload.role_id = selectedRoleId;
    } else if (selectedDeptId) {
      payload.department_id = selectedDeptId;
    } else {
      alert("Please select a role or department.");
      return;
    }

    grantAccessMutation.mutate({ id: activeDbId, payload });
  };

  const handleOpenSchema = (dbConn: any) => {
    setSchemaDbId(dbConn.id);
    setSchemaDbName(dbConn.name);
    setIsSchemaModalOpen(true);
  };

  // Filter connections list
  const filteredDbs = databases.filter(db => 
    db.name.toLowerCase().includes(search.toLowerCase()) ||
    db.database_name.toLowerCase().includes(search.toLowerCase()) ||
    db.host.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 text-slate-800 dark:text-slate-100 animate-in fade-in duration-300">
      
      {/* Header */}
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Database className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
            External Databases
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Connect and manage external PostgreSQL and MySQL databases. Authorized employees can query them via chat.
          </p>
        </div>
        <button 
          onClick={handleOpenCreate}
          className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white px-4 py-2.5 rounded-xl transition-colors font-semibold shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Database
        </button>
      </div>

      {/* Recommended control banner */}
      <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-2xl p-4 flex gap-3 text-sm text-amber-800 dark:text-amber-300">
        <AlertCircle className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-500" />
        <div>
          <span className="font-semibold">Security Suggestion:</span> We highly recommend providing a <strong>read-only</strong> database user for connections. This adds an additional layer of security on your database host in addition to our application-level safety query bounds.
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search connections..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 pl-10 pr-4 py-2.5 text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 transition-all"
          />
        </div>
      </div>

      {/* Database Grid */}
      {isDbsLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2].map((i) => (
            <div key={i} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm animate-pulse h-48" />
          ))}
        </div>
      ) : filteredDbs.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center shadow-sm">
          <Database className="w-12 h-12 text-slate-300 dark:text-slate-700 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">No database connections</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
            Get started by adding your first external PostgreSQL or MySQL database connection.
          </p>
          <button 
            onClick={handleOpenCreate}
            className="mt-4 inline-flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white px-4 py-2.5 rounded-xl transition-colors font-semibold"
          >
            <Plus className="w-4 h-4" />
            Add Database
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDbs.map((dbConn) => (
            <div 
              key={dbConn.id} 
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow relative flex flex-col justify-between"
            >
              <div>
                {/* Header */}
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-lg text-slate-900 dark:text-slate-100 truncate max-w-[200px]">
                      {dbConn.name}
                    </h3>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 mt-1">
                      {dbConn.engine}
                    </span>
                  </div>
                  
                  {/* Status Indicator */}
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${
                    dbConn.status === 'active' 
                      ? 'bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border-emerald-250 dark:border-emerald-900/50' 
                      : 'bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-400 border-rose-250 dark:border-rose-900/50'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${dbConn.status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                    {dbConn.status === 'active' ? 'Healthy' : 'Error'}
                  </span>
                </div>

                {/* Details */}
                <div className="space-y-2 text-sm text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 pt-3 mb-6">
                  <div className="flex justify-between">
                    <span>Host:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{dbConn.host}:{dbConn.port}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Database:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[150px]">{dbConn.database_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Last Sync:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{formatDate(dbConn.last_synced_at)}</span>
                  </div>
                  {dbConn.last_error && (
                    <div className="text-xs text-rose-500 dark:text-rose-400 border-t border-rose-100 dark:border-rose-950/20 pt-2 mt-2 break-all line-clamp-2" title={dbConn.last_error}>
                      Error: {dbConn.last_error}
                    </div>
                  )}
                </div>
              </div>

              {/* Actions Footer */}
              <div className="flex items-center gap-1.5 border-t border-slate-100 dark:border-slate-800 pt-4 mt-auto">
                <button
                  onClick={() => handleOpenSchema(dbConn)}
                  className="flex-1 flex items-center justify-center gap-1 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 p-2 rounded-lg text-xs font-semibold transition-colors"
                  title="View reflected schema"
                >
                  <Eye className="w-3.5 h-3.5" />
                  Schema
                </button>
                <button
                  onClick={() => handleOpenAccess(dbConn)}
                  className="flex-1 flex items-center justify-center gap-1 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 p-2 rounded-lg text-xs font-semibold transition-colors"
                  title="Manage access grants"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Access
                </button>
                <button
                  onClick={() => refreshSchemaMutation.mutate(dbConn.id)}
                  disabled={refreshSchemaMutation.isPending}
                  className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors shrink-0 disabled:opacity-50"
                  title="Force schema refresh sync"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshSchemaMutation.isPending ? 'animate-spin' : ''}`} />
                </button>
                <button
                  onClick={() => handleOpenEdit(dbConn)}
                  className="p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors shrink-0 text-xs font-semibold"
                  title="Edit connection details"
                >
                  Edit
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Are you sure you want to delete database "${dbConn.name}"?`)) {
                      deleteMutation.mutate(dbConn.id);
                    }
                  }}
                  className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg transition-colors shrink-0"
                  title="Delete database connection"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ─── ADD/EDIT CONNECTION FORM MODAL ─── */}
      {isFormOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                {connId ? 'Edit Database Connection' : 'Add Database Connection'}
              </h2>
              <button onClick={() => setIsFormOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                  Connection Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Production Analytics"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Engine Type *
                  </label>
                  <select
                    value={engine}
                    onChange={(e) => {
                      setEngine(e.target.value);
                      setPort(e.target.value === 'mysql' ? 3306 : 5432);
                    }}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Port *
                  </label>
                  <input
                    type="number"
                    value={port}
                    onChange={(e) => setPort(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Host IP / Domain *
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 192.168.1.10 or localhost"
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Database Name *
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. app_db"
                    value={databaseName}
                    onChange={(e) => setDatabaseName(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Username *
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. readonly_user"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Password {connId && '(Leave blank to keep)'} *
                  </label>
                  <input
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                  SSL Mode
                </label>
                <select
                  value={sslMode}
                  onChange={(e) => setSslMode(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25"
                >
                  <option value="prefer">Prefer (Default)</option>
                  <option value="require">Require</option>
                  <option value="disable">Disable</option>
                  <option value="allow">Allow</option>
                </select>
              </div>

              {/* Live Test Connection Actions & Alerts */}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-3">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={isTesting}
                  className="w-full flex items-center justify-center gap-2 border border-indigo-200 dark:border-indigo-900/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 py-2.5 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${isTesting ? 'animate-spin' : ''}`} />
                  {isTesting ? 'Testing reachability...' : 'Test Connection'}
                </button>

                {testResult && (
                  <div className={`p-3.5 rounded-xl border flex gap-2.5 text-sm ${
                    testResult.success 
                      ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/50 text-emerald-800 dark:text-emerald-400' 
                      : 'bg-rose-50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/50 text-rose-800 dark:text-rose-400'
                  }`}>
                    {testResult.success ? (
                      <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-5 h-5 shrink-0 text-rose-600 dark:text-rose-400" />
                    )}
                    <span className="font-medium break-all">{testResult.message}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex gap-3 px-6 py-4 bg-slate-50 dark:bg-slate-900/50 border-t border-slate-100 dark:border-slate-800 rounded-b-2xl">
              <button
                type="button"
                onClick={() => setIsFormOpen(false)}
                className="flex-1 border border-slate-200 dark:border-slate-800 rounded-xl py-2.5 text-sm font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveConnection}
                disabled={createMutation.isPending || updateMutation.isPending}
                className="flex-1 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-850 dark:hover:bg-indigo-650 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Connection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── ACCESS MANAGEMENT MODAL ─── */}
      {isAccessModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  Database Access: {activeDbName}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">Define who can query this database and tables.</p>
              </div>
              <button onClick={() => setIsAccessModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Grant Access Form */}
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Grant New Access</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Grant to Role
                  </label>
                  <select
                    value={selectedRoleId}
                    onChange={(e) => {
                      setSelectedRoleId(e.target.value);
                      setSelectedDeptId('');
                    }}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none"
                  >
                    <option value="">-- Select Role --</option>
                    {roles.map((r: any) => (
                      <option key={r.id} value={r.id}>{r.name} {r.is_admin ? '(Admin)' : ''}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    OR Grant to Department
                  </label>
                  <select
                    value={selectedDeptId}
                    onChange={(e) => {
                      setSelectedDeptId(e.target.value);
                      setSelectedRoleId('');
                    }}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none"
                  >
                    <option value="">-- Select Department --</option>
                    {departments.map((d: any) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                  Table Scope
                </label>
                <select
                  value={selectedTable}
                  onChange={(e) => setSelectedTable(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3.5 py-2 text-sm focus:outline-none"
                >
                  <option value="">Whole Database (All Tables)</option>
                  {dbTables.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={handleGrantAccess}
                disabled={grantAccessMutation.isPending}
                className="w-full bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-650 text-white rounded-xl py-2 text-sm font-semibold transition-colors disabled:opacity-50"
              >
                Grant Access
              </button>
            </div>

            {/* List of Active Policies */}
            <div className="p-6">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Active Access Policies</h3>
              
              {accessPolicies.length === 0 ? (
                <p className="text-sm text-slate-400 italic text-center py-4">No access policies configured yet.</p>
              ) : (
                <div className="border border-slate-150 dark:border-slate-800 rounded-xl overflow-hidden text-sm">
                  <div className="grid grid-cols-12 gap-2 bg-slate-50 dark:bg-slate-900/50 px-4 py-2.5 font-semibold text-slate-500 dark:text-slate-400 border-b border-slate-150 dark:border-slate-800">
                    <div className="col-span-4">Granted Role</div>
                    <div className="col-span-3">Via Type</div>
                    <div className="col-span-3">Table Scope</div>
                    <div className="col-span-2 text-right">Action</div>
                  </div>
                  <div className="divide-y divide-slate-150 dark:divide-slate-800">
                    {accessPolicies.map((policy) => (
                      <div key={policy.id} className="grid grid-cols-12 gap-2 px-4 py-3 items-center hover:bg-slate-50/50 dark:hover:bg-slate-900/10">
                        <div className="col-span-4 font-medium text-slate-800 dark:text-slate-200">
                          {policy.role_name}
                        </div>
                        <div className="col-span-3 text-slate-500 dark:text-slate-400 flex flex-col">
                          <span className="capitalize">{policy.granted_via}</span>
                          {policy.granted_via === 'inherited' && (
                            <span className="text-[10px] text-indigo-500">via: {policy.inherited_from_role_name}</span>
                          )}
                          {policy.granted_via === 'department' && (
                            <span className="text-[10px] text-emerald-500">dept: {policy.granted_via_department_name}</span>
                          )}
                        </div>
                        <div className="col-span-3 font-mono text-xs text-slate-600 dark:text-slate-300">
                          {policy.table_name ? (
                            <span className="inline-flex items-center gap-1 bg-slate-100 dark:bg-slate-850 px-2 py-0.5 rounded text-[11px] font-bold">
                              <Lock className="w-2.5 h-2.5" />
                              {policy.table_name}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 px-2 py-0.5 rounded text-[11px] font-bold">
                              <Unlock className="w-2.5 h-2.5" />
                              db: all
                            </span>
                          )}
                        </div>
                        <div className="col-span-2 text-right">
                          <button
                            onClick={() => revokeAccessMutation.mutate({ id: activeDbId!, policyId: policy.id })}
                            className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20 p-1.5 rounded-lg transition-colors"
                            title="Revoke access grant"
                          >
                            <Trash2 className="w-4 h-4 inline-block" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── SCHEMA VIEWER MODAL ─── */}
      {isSchemaModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Database className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  Reflected Database Schema: {schemaDbName}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">Reflected list of tables, columns, primary keys, and foreign keys.</p>
              </div>
              <button onClick={() => setIsSchemaModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Schema Tables List */}
            <div className="p-6 space-y-6">
              {!schemaCache.tables || schemaCache.tables.length === 0 ? (
                <div className="text-center py-12">
                  <Database className="w-12 h-12 text-slate-350 dark:text-slate-650 mx-auto mb-3 animate-bounce" />
                  <p className="text-sm text-slate-400 italic">No schema cache reflected yet. Try running 'Refresh Schema'.</p>
                </div>
              ) : (
                schemaCache.tables.map((table: any) => (
                  <div key={table.name} className="border border-slate-150 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
                    {/* Table Title */}
                    <div className="bg-slate-50 dark:bg-slate-900/60 px-5 py-3 border-b border-slate-150 dark:border-slate-800 flex justify-between items-center">
                      <h3 className="font-bold text-indigo-600 dark:text-indigo-400 font-mono text-sm">
                        {table.name}
                      </h3>
                      <span className="text-[11px] px-2 py-0.5 bg-slate-200 dark:bg-slate-800 rounded font-semibold text-slate-500">
                        {table.columns.length} columns
                      </span>
                    </div>

                    {/* Columns List */}
                    <div className="p-4 bg-white dark:bg-slate-900 space-y-3">
                      <div className="grid grid-cols-12 gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-100 dark:border-slate-800/40 pb-2">
                        <div className="col-span-5">Column Name</div>
                        <div className="col-span-4">Type</div>
                        <div className="col-span-3">Properties</div>
                      </div>
                      <div className="space-y-2.5 divide-y divide-slate-100/50 dark:divide-slate-800/20">
                        {table.columns.map((col: any) => {
                          const isPk = table.primary_key?.includes(col.name);
                          const fkRef = table.foreign_keys?.find((fk: any) => fk.constrained_columns.includes(col.name));
                          return (
                            <div key={col.name} className="grid grid-cols-12 gap-2 text-xs pt-2.5 font-mono">
                              <div className="col-span-5 font-semibold text-slate-800 dark:text-slate-200">
                                {col.name}
                              </div>
                              <div className="col-span-4 text-slate-500 dark:text-slate-400">
                                {col.type}
                              </div>
                              <div className="col-span-3 flex flex-wrap gap-1">
                                {isPk && (
                                  <span className="bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/30 px-1.5 py-0.5 rounded text-[10px] font-bold">
                                    PK
                                  </span>
                                )}
                                {!col.nullable && (
                                  <span className="bg-slate-150 dark:bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded text-[10px] font-bold">
                                    NOT NULL
                                  </span>
                                )}
                                {fkRef && (
                                  <span 
                                    className="bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-900/30 px-1.5 py-0.5 rounded text-[10px] font-bold cursor-help"
                                    title={`References ${fkRef.referred_table}(${fkRef.referred_columns})`}
                                  >
                                    FK: {fkRef.referred_table}
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DatabasesPage;
