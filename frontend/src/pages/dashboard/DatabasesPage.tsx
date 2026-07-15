import React, { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  Database, 
  Plus, 
  RefreshCw, 
  Trash2, 
  ShieldCheck, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Search, 
  Lock, 
  Unlock, 
  Edit,
  ChevronDown,
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
  const navigate = useNavigate();

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
  const [engineFilter, setEngineFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isAccessModalOpen, setIsAccessModalOpen] = useState(false);

  // Dropdown states & refs
  const [isEngineFilterDropdownOpen, setIsEngineFilterDropdownOpen] = useState(false);
  const [isStatusDropdownOpen, setIsStatusDropdownOpen] = useState(false);
  const engineFilterDropdownRef = useRef<HTMLDivElement>(null);
  const statusFilterDropdownRef = useRef<HTMLDivElement>(null);

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
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
  const roleDropdownRef = useRef<HTMLDivElement>(null);

  const [selectedDeptIds, setSelectedDeptIds] = useState<string[]>([]);
  const [isDeptDropdownOpen, setIsDeptDropdownOpen] = useState(false);
  const deptDropdownRef = useRef<HTMLDivElement>(null);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [isTableDropdownOpen, setIsTableDropdownOpen] = useState(false);
  const tableDropdownRef = useRef<HTMLDivElement>(null);
  const [dbTables, setDbTables] = useState<string[]>([]);
  const [dbSchema, setDbSchema] = useState<any>(null);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [isColDropdownOpen, setIsColDropdownOpen] = useState(false);
  const colDropdownRef = useRef<HTMLDivElement>(null);

  const getAvailableColumns = () => {
    if (!dbSchema || !dbSchema.tables) return [];
    
    const cols: any[] = [];
    dbSchema.tables.forEach((tbl: any) => {
      if (selectedTables.includes(tbl.name)) {
        tbl.columns.forEach((c: any) => {
          cols.push({
            table: tbl.name,
            column: c.name,
            fullName: `${tbl.name}.${c.name}`
          });
        });
      }
    });
    return cols;
  };

  const availableCols = getAvailableColumns();

  useEffect(() => {
    if (dbSchema) {
      const cols = getAvailableColumns();
      setSelectedColumns(cols.map((c: any) => c.fullName));
    } else {
      setSelectedColumns([]);
    }
    setIsColDropdownOpen(false);
  }, [selectedTables, dbSchema]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (colDropdownRef.current && !colDropdownRef.current.contains(event.target as Node)) {
        setIsColDropdownOpen(false);
      }
      if (tableDropdownRef.current && !tableDropdownRef.current.contains(event.target as Node)) {
        setIsTableDropdownOpen(false);
      }
      if (roleDropdownRef.current && !roleDropdownRef.current.contains(event.target as Node)) {
        setIsRoleDropdownOpen(false);
      }
      if (deptDropdownRef.current && !deptDropdownRef.current.contains(event.target as Node)) {
        setIsDeptDropdownOpen(false);
      }
      if (engineFilterDropdownRef.current && !engineFilterDropdownRef.current.contains(event.target as Node)) {
        setIsEngineFilterDropdownOpen(false);
      }
      if (statusFilterDropdownRef.current && !statusFilterDropdownRef.current.contains(event.target as Node)) {
        setIsStatusDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Access policies query
  const { data: accessPolicies = [], refetch: refetchAccess } = useQuery({
    queryKey: ['database-access', activeDbId],
    queryFn: () => databaseService.listAccessPolicies(activeDbId!),
    enabled: !!activeDbId,
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
      setSelectedRoleIds([]);
      setSelectedDeptIds([]);
      setSelectedTables([]);
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
    setSelectedRoleIds([]);
    setSelectedDeptIds([]);
    setSelectedTables([]);
    setSelectedColumns([]);
    setDbSchema(null);
    
    // Fetch tables for table-scoped grants from schema cache
    try {
      const schema = await databaseService.getDatabaseSchema(dbConn.id);
      const tablesList = schema.tables?.map((t: any) => t.name) || [];
      setDbTables(tablesList);
      setDbSchema(schema);
      setSelectedTables(tablesList);
    } catch (e) {
      setDbTables([]);
      setDbSchema(null);
    }
    
    setIsAccessModalOpen(true);
  };

  const handleGrantAccess = () => {
    if (!activeDbId) return;
    if (selectedTables.length === 0) {
      alert("Please select at least one table.");
      return;
    }

    const isAllTablesSelected = selectedTables.length === dbTables.length;
    const payload: any = {
      table_name: null,
      table_names: isAllTablesSelected ? null : selectedTables,
      columns: selectedColumns,
    };
    if (selectedRoleIds.length > 0) {
      payload.role_ids = selectedRoleIds;
    } else if (selectedDeptIds.length > 0) {
      payload.department_ids = selectedDeptIds;
    } else {
      alert("Please select at least one role or department.");
      return;
    }

    grantAccessMutation.mutate({ id: activeDbId, payload });
  };


  // Filter connections list
  const filteredDbs = databases.filter(db => {
    const matchesSearch = 
      db.name.toLowerCase().includes(search.toLowerCase()) ||
      db.database_name.toLowerCase().includes(search.toLowerCase()) ||
      db.host.toLowerCase().includes(search.toLowerCase());
    
    const matchesEngine = !engineFilter || db.engine === engineFilter;
    const matchesStatus = !statusFilter || db.status === statusFilter;
    const matchesDate = !dateFilter || db.created_at.startsWith(dateFilter);

    return matchesSearch && matchesEngine && matchesStatus && matchesDate;
  });

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
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard/databases/analytics')}
            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline transition-all cursor-pointer font-sans bg-transparent border-0 px-2 py-1"
          >
            Show Analytics
          </button>
          <button 
            onClick={handleOpenCreate}
            className="flex items-center gap-2 bg-indigo-700 dark:bg-indigo-500 hover:bg-indigo-800 dark:hover:bg-indigo-600 text-white px-4 py-2.5 rounded-xl transition-colors font-semibold shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Add Database
          </button>
        </div>
      </div>

      {/* Recommended control banner */}
      <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-2xl p-4 flex gap-3 text-sm text-amber-800 dark:text-amber-300">
        <AlertCircle className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-500" />
        <div>
          <span className="font-semibold">Security Suggestion:</span> We highly recommend providing a <strong>read-only</strong> database user for connections. This adds an additional layer of security on your database host in addition to our application-level safety query bounds.
        </div>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search connections by name, host, or database..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 transition-all"
          />
        </div>

        <div className="hidden lg:block w-px h-8 bg-slate-200 dark:bg-slate-800 mx-1 shrink-0"></div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-end gap-3 w-full lg:w-auto shrink-0">
          {/* Engine Filter */}
          <div className="relative inline-block text-left" ref={engineFilterDropdownRef}>
            <button
              onClick={() => setIsEngineFilterDropdownOpen(!isEngineFilterDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[128px] cursor-pointer shadow-sm"
            >
              <span>
                {engineFilter === '' && 'All Engines'}
                {engineFilter === 'postgresql' && 'PostgreSQL'}
                {engineFilter === 'mysql' && 'MySQL'}
              </span>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isEngineFilterDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isEngineFilterDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-40 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {([['', 'All Engines'], ['postgresql', 'PostgreSQL'], ['mysql', 'MySQL']] as const).map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => {
                      setEngineFilter(val);
                      setIsEngineFilterDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      engineFilter === val ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15' : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Status Filter */}
          <div className="relative inline-block text-left" ref={statusFilterDropdownRef}>
            <button
              onClick={() => setIsStatusDropdownOpen(!isStatusDropdownOpen)}
              type="button"
              className="inline-flex items-center justify-between gap-2 px-3.5 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-all select-none outline-none min-w-[140px] cursor-pointer shadow-sm"
            >
              <span>
                {statusFilter === '' && 'All Statuses'}
                {statusFilter === 'active' && 'Healthy'}
                {statusFilter === 'error' && 'Error'}
              </span>
              <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isStatusDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isStatusDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-30 overflow-hidden py-1">
                {([['', 'All Statuses'], ['active', 'Healthy'], ['error', 'Error']] as const).map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => {
                      setStatusFilter(val);
                      setIsStatusDropdownOpen(false);
                    }}
                    type="button"
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      statusFilter === val ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50/30 dark:bg-indigo-950/15' : 'text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Date Filter */}
          <div className="relative shrink-0 w-44">
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 text-sm font-semibold rounded-xl pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            />
            {dateFilter && (
              <button
                onClick={() => setDateFilter('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-650 dark:hover:text-slate-200"
                title="Clear date"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
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
                  <div className="flex flex-row gap-3">
                    <h3 className="font-bold text-lg text-slate-900 dark:text-slate-100 truncate max-w-[200px]">
                      {dbConn.name}
                    </h3>

                  {/* Status Indicator */}
                  <span className={`inline-flex items-center gap-1 px-2 rounded-full text-xs font-medium border ${
                    dbConn.status === 'active' 
                      ? 'bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border-emerald-250 dark:border-emerald-900/50' 
                      : 'bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-400 border-rose-250 dark:border-rose-900/50'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${dbConn.status === 'active' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                    {dbConn.status === 'active' ? 'Healthy' : 'Error'}
                  </span>
                  
                  </div>

                <button
                  onClick={() => refreshSchemaMutation.mutate(dbConn.id)}
                  disabled={refreshSchemaMutation.isPending && refreshSchemaMutation.variables === dbConn.id}
                  className="flex items-center justify-center gap-1 p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs rounded-lg font-semibold transition-colors shrink-0 disabled:opacity-50"
                  title="Force schema refresh sync"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshSchemaMutation.isPending && refreshSchemaMutation.variables === dbConn.id ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                </div>

                {/* Details */}
                <div className="space-y-2 text-sm text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 pt-2 mb-4">
                  <div className="flex justify-between">
                    <span>Engine:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 capitalize">{dbConn.engine}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Host:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{dbConn.host}:{dbConn.port}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Database:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[150px]">{dbConn.database_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Tables:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{dbConn.table_count ?? 0}</span>
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
              <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-2 mt-auto">
                <div className="flex items-center gap-2">


                <button
                  onClick={() => handleOpenAccess(dbConn)}
                  className="flex items-center justify-center gap-1 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 p-2 rounded-lg text-xs font-semibold transition-colors"
                  title="Manage access grants"
                  >
                  {/* <ShieldCheck className="w-3.5 h-3.5" /> */}
                  Manage Access
                </button>
                  </div>
                  <div className="flex items-center gap-2">

                <button
                  onClick={() => handleOpenEdit(dbConn)}
                  className="flex items-center justify-center gap-1 p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors shrink-0 text-xs font-semibold"
                  title="Edit connection details"
                  >
                  <Edit className="w-3.5 h-3.5" />
                  Edit
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Are you sure you want to delete database "${dbConn.name}"?`)) {
                      deleteMutation.mutate(dbConn.id);
                    }
                  }}
                  className="flex items-center justify-center gap-1 p-2 text-slate-600 dark:text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/40 dark:hover:text-red-400 rounded-lg transition-colors text-xs font-semibold shrink-0"
                  title="Delete database connection"
                  >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
                  </div>
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
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl animate-in zoom-in-95 duration-200 overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-t-2xl z-10">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                  Database Access: {activeDbName}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">Define who can query this database and tables.</p>
              </div>
              <button onClick={() => setIsAccessModalOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 flex-shrink-0">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Content Container */}
            <div className="overflow-y-auto flex-1 custom-scrollbar">

            {/* Grant Access Form */}
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Grant New Access</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Grant to Role
                  </label>
                  <div ref={roleDropdownRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
                      className="w-full flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25 cursor-pointer transition-all"
                    >
                      <span className="truncate">
                        {selectedRoleIds.length === 0
                          ? "-- Select Role(s) --"
                          : selectedRoleIds.length === roles.length
                          ? "All Roles Selected"
                          : `${selectedRoleIds.length} / ${roles.length} Roles Selected`}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${isRoleDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {isRoleDropdownOpen && (
                      <div className="absolute right-0 left-0 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 space-y-1">
                        <div className="flex items-center justify-between px-2 py-1 border-b border-slate-100 dark:border-slate-800 pb-1.5 mb-1.5 text-xs text-indigo-650 dark:text-indigo-400 font-semibold">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedDeptIds([]);
                              setSelectedRoleIds(roles.map((r: any) => r.id));
                            }}
                            className="hover:underline"
                          >
                            Select All
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedRoleIds([])}
                            className="hover:underline"
                          >
                            Clear All
                          </button>
                        </div>
                        {roles.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-2">No roles available</p>
                        ) : (
                          roles.map((r: any) => {
                            const isChecked = selectedRoleIds.includes(r.id);
                            return (
                              <label
                                key={r.id}
                                className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-lg cursor-pointer text-sm select-none"
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {
                                    setSelectedDeptIds([]);
                                    if (isChecked) {
                                      setSelectedRoleIds(selectedRoleIds.filter(item => item !== r.id));
                                    } else {
                                      setSelectedRoleIds([...selectedRoleIds, r.id]);
                                    }
                                  }}
                                  className="rounded border-slate-300 dark:border-slate-700 text-indigo-650 focus:ring-indigo-500/25 w-4 h-4 cursor-pointer"
                                />
                                <span className="text-slate-700 dark:text-slate-300 truncate font-semibold">
                                  {r.name} {r.is_admin ? '(Admin)' : ''}
                                </span>
                              </label>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    OR Grant to Department
                  </label>
                  <div ref={deptDropdownRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setIsDeptDropdownOpen(!isDeptDropdownOpen)}
                      className="w-full flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25 cursor-pointer transition-all"
                    >
                      <span className="truncate">
                        {selectedDeptIds.length === 0
                          ? "-- Select Department(s) --"
                          : selectedDeptIds.length === departments.length
                          ? "All Departments Selected"
                          : `${selectedDeptIds.length} / ${departments.length} Depts Selected`}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${isDeptDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {isDeptDropdownOpen && (
                      <div className="absolute right-0 left-0 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 space-y-1">
                        <div className="flex items-center justify-between px-2 py-1 border-b border-slate-100 dark:border-slate-800 pb-1.5 mb-1.5 text-xs text-indigo-650 dark:text-indigo-400 font-semibold">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedRoleIds([]);
                              setSelectedDeptIds(departments.map((d: any) => d.id));
                            }}
                            className="hover:underline"
                          >
                            Select All
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedDeptIds([])}
                            className="hover:underline"
                          >
                            Clear All
                          </button>
                        </div>
                        {departments.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-2">No departments available</p>
                        ) : (
                          departments.map((d: any) => {
                            const isChecked = selectedDeptIds.includes(d.id);
                            return (
                              <label
                                key={d.id}
                                className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-lg cursor-pointer text-sm select-none"
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {
                                    setSelectedRoleIds([]);
                                    if (isChecked) {
                                      setSelectedDeptIds(selectedDeptIds.filter(item => item !== d.id));
                                    } else {
                                      setSelectedDeptIds([...selectedDeptIds, d.id]);
                                    }
                                  }}
                                  className="rounded border-slate-300 dark:border-slate-700 text-indigo-650 focus:ring-indigo-500/25 w-4 h-4 cursor-pointer"
                                />
                                <span className="text-slate-700 dark:text-slate-300 truncate font-semibold">
                                  {d.name}
                                </span>
                              </label>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Table Scope
                  </label>
                  <div ref={tableDropdownRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setIsTableDropdownOpen(!isTableDropdownOpen)}
                      className="w-full flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25 cursor-pointer transition-all"
                    >
                      <span className="truncate">
                        {selectedTables.length === dbTables.length
                          ? "Whole Database (All Tables)"
                          : selectedTables.length === 0
                          ? "No Tables Selected"
                          : `${selectedTables.length} / ${dbTables.length} Tables`}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${isTableDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {isTableDropdownOpen && (
                      <div className="absolute right-0 left-0 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 space-y-1">
                        <div className="flex items-center justify-between px-2 py-1 border-b border-slate-100 dark:border-slate-800 pb-1.5 mb-1.5 text-xs text-indigo-650 dark:text-indigo-400 font-semibold">
                          <button
                            type="button"
                            onClick={() => setSelectedTables(dbTables)}
                            className="hover:underline"
                          >
                            Select All
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedTables([])}
                            className="hover:underline"
                          >
                            Clear All
                          </button>
                        </div>
                        {dbTables.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-2">No tables available</p>
                        ) : (
                          dbTables.map((t) => {
                            const isChecked = selectedTables.includes(t);
                            return (
                              <label
                                key={t}
                                className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-lg cursor-pointer text-sm select-none"
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {
                                    if (isChecked) {
                                      setSelectedTables(selectedTables.filter(item => item !== t));
                                    } else {
                                      setSelectedTables([...selectedTables, t]);
                                    }
                                  }}
                                  className="rounded border-slate-300 dark:border-slate-700 text-indigo-650 focus:ring-indigo-500/25 w-4 h-4 cursor-pointer"
                                />
                                <span className="text-slate-700 dark:text-slate-300 truncate font-mono text-xs">
                                  {t}
                                </span>
                              </label>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                    Column Scope
                  </label>
                  <div ref={colDropdownRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setIsColDropdownOpen(!isColDropdownOpen)}
                      className="w-full flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/25 cursor-pointer transition-all"
                    >
                      <span className="truncate">
                        {selectedColumns.length === availableCols.length
                          ? "All Columns Selected"
                          : `${selectedColumns.length} / ${availableCols.length} Columns`}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${isColDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {isColDropdownOpen && (
                      <div className="absolute right-0 left-0 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 space-y-1">
                        <div className="flex items-center justify-between px-2 py-1 border-b border-slate-100 dark:border-slate-800 pb-1.5 mb-1.5 text-xs text-indigo-650 dark:text-indigo-400 font-semibold">
                          <button
                            type="button"
                            onClick={() => setSelectedColumns(availableCols.map((c: any) => c.fullName))}
                            className="hover:underline"
                          >
                            Select All
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedColumns([])}
                            className="hover:underline"
                          >
                            Clear All
                          </button>
                        </div>
                        {availableCols.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-2">No columns available</p>
                        ) : (
                          (() => {
                            const groups: { [key: string]: any[] } = {};
                            availableCols.forEach((c: any) => {
                              if (!groups[c.table]) {
                                groups[c.table] = [];
                              }
                              groups[c.table].push(c);
                            });

                            return Object.keys(groups).map((tableName) => (
                              <div key={tableName} className="space-y-1">
                                {selectedTables.length > 1 && (
                                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-2 pt-2 pb-1 border-t border-slate-100 dark:border-slate-800/50 first:border-0">
                                    {tableName}
                                  </div>
                                )}
                                {groups[tableName].map((c: any) => {
                                  const isChecked = selectedColumns.includes(c.fullName);
                                  return (
                                    <label
                                      key={c.fullName}
                                      className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-lg cursor-pointer text-sm select-none"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={() => {
                                          if (isChecked) {
                                            setSelectedColumns(selectedColumns.filter(item => item !== c.fullName));
                                          } else {
                                            setSelectedColumns([...selectedColumns, c.fullName]);
                                          }
                                        }}
                                        className="rounded border-slate-300 dark:border-slate-700 text-indigo-650 focus:ring-indigo-500/25 w-4 h-4 cursor-pointer"
                                      />
                                      <span className="text-slate-700 dark:text-slate-300 truncate font-mono text-xs" title={c.fullName}>
                                        {c.column}
                                      </span>
                                    </label>
                                  );
                                })}
                              </div>
                            ));
                          })()
                        )}
                      </div>
                    )}
                  </div>
                </div>
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
                <p className="text-sm text-slate-400 text-center py-4">No access policies configured yet.</p>
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
                        <div className="col-span-3 font-mono text-xs text-slate-600 dark:text-slate-300 flex flex-col items-start gap-1">
                          {policy.table_name ? (
                            <span className="inline-flex items-center gap-1 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-[11px] font-bold">
                              <Lock className="w-2.5 h-2.5" />
                              {policy.table_name}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 px-2 py-0.5 rounded text-[11px] font-bold">
                              <Unlock className="w-2.5 h-2.5" />
                              db: all
                            </span>
                          )}
                          {policy.columns && policy.columns.length > 0 && (
                            <span className="text-[10px] text-slate-400 dark:text-slate-500 font-sans mt-0.5">
                              Columns: {policy.columns.length} allowed
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
        </div>
      )}

    </div>
  );
};

export default DatabasesPage;
