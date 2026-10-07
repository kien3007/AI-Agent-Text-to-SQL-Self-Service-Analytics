"use client";

import React, { useState } from "react";
import {
  Database,
  X,
  RefreshCw,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  Server,
  Layers,
  Sparkles,
  Search,
  Check,
  RotateCcw,
} from "lucide-react";

interface ConnectDatabaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeDomainId?: string;
  initialTab?: "connect" | "ingest";
  onSuccess?: (newDomainId?: string) => void;
}

export default function ConnectDatabaseModal({
  isOpen,
  onClose,
  activeDomainId = "ecommerce",
  initialTab = "connect",
  onSuccess,
}: ConnectDatabaseModalProps) {
  const [activeTab, setActiveTab] = useState<"connect" | "ingest">(initialTab);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<any | null>(null);

  // Connect form state
  const [dialect, setDialect] = useState<string>("postgresql");
  const [connectionUrl, setConnectionUrl] = useState<string>("");
  const [domainId, setDomainId] = useState<string>("");
  const [displayName, setDisplayName] = useState<string>("");
  const [schemaName, setSchemaName] = useState<string>("");
  const [saveYaml, setSaveYaml] = useState<boolean>(true);
  const [registerAllSchemas, setRegisterAllSchemas] = useState<boolean>(false);

  // Step 2 & 3: Database & Schema Inspection Discovery State
  const [isInspecting, setIsInspecting] = useState<boolean>(false);
  const [connectionTested, setConnectionTested] = useState<boolean>(false);
  const [inspectMessage, setInspectMessage] = useState<string | null>(null);
  const [discoveredDatabases, setDiscoveredDatabases] = useState<string[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState<string>("");
  const [discoveredSchemas, setDiscoveredSchemas] = useState<string[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<string>("");

  // Ingest form state
  const [targetDomain, setTargetDomain] = useState<string>(activeDomainId);
  const [ingestSourceUrl, setIngestSourceUrl] = useState<string>("");
  const [ingestSchema, setIngestSchema] = useState<string>("");
  const [syncMode, setSyncMode] = useState<"full_refresh" | "append">("full_refresh");

  if (!isOpen) return null;

  const handleDialectChange = (newDialect: string) => {
    setDialect(newDialect);
    setConnectionTested(false);
    setInspectMessage(null);
    setDiscoveredDatabases([]);
    setSelectedDatabase("");
    setDiscoveredSchemas([]);
    setSelectedSchema("");

    switch (newDialect) {
      case "postgresql":
        setConnectionUrl("postgresql://postgres:postgres@localhost:5432/my_database");
        break;
      case "mysql":
        setConnectionUrl("mysql+pymysql://root:password@localhost:3306/my_database");
        break;
      case "mssql":
        setConnectionUrl("mssql+pymssql://sa:Password123@localhost:1433/my_database");
        break;
      case "duckdb":
        setConnectionUrl("./data/warehouse.duckdb");
        break;
      case "sqlite":
        setConnectionUrl("./data/analytics.db");
        break;
      default:
        break;
    }
  };

  // Bước 1: Kiểm tra kết nối và tự động lấy danh sách Database & Schema từ server
  const handleInspectConnection = async (overrideDb?: string) => {
    if (!connectionUrl.trim()) {
      setError("Vui lòng nhập chuỗi kết nối CSDL (Connection URL hoặc File Path).");
      return;
    }

    setIsInspecting(true);
    setError(null);
    setInspectMessage(null);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("jwt_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const targetDb = overrideDb !== undefined ? overrideDb : selectedDatabase;
      const res = await fetch("/api/domains/inspect-connection", {
        method: "POST",
        headers,
        body: JSON.stringify({
          connection_url: connectionUrl.trim(),
          database_name: targetDb || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Lỗi kiểm tra kết nối (${res.status})`);
      }

      setConnectionTested(true);
      setInspectMessage(data.message || "Kết nối CSDL thành công!");

      const dbs = data.databases || [];
      setDiscoveredDatabases(dbs);

      const currentDb = data.current_database || (dbs.length > 0 ? dbs[0] : "");
      setSelectedDatabase(currentDb);

      const schemas = data.schemas || [];
      setDiscoveredSchemas(schemas);

      const defSchema = data.default_schema || (schemas.length > 0 ? schemas[0] : "main");
      setSelectedSchema(defSchema);
      setSchemaName(defSchema);

      // Tự động gợi ý Domain ID và Tên hiển thị
      const cleanDbName = (currentDb || "db").toLowerCase().replace(/[^a-z0-9_]/g, "_");
      const cleanSchemaName = (defSchema || "").toLowerCase().replace(/[^a-z0-9_]/g, "_");
      const isGenericSchema = ["main", "dbo", "public", ""].includes(cleanSchemaName);

      const suggestedDomain = !isGenericSchema && cleanSchemaName
        ? `${cleanDbName}_${cleanSchemaName}`
        : cleanDbName;

      setDomainId(suggestedDomain);

      const titleDb = (currentDb || "Database").replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
      const titleSchema = !isGenericSchema && defSchema ? ` - ${defSchema}` : "";
      setDisplayName(`${titleDb}${titleSchema}`);
    } catch (err: any) {
      setError(err.message || "Không thể kết nối và khám phá CSDL.");
      setConnectionTested(false);
    } finally {
      setIsInspecting(false);
    }
  };

  // Khi chọn một Database khác từ danh sách
  const handleDatabaseChange = (dbName: string) => {
    setSelectedDatabase(dbName);
    handleInspectConnection(dbName);
  };

  // Khi chọn một Schema từ danh sách
  const handleSchemaChange = (schema: string) => {
    setSelectedSchema(schema);
    const isAll = schema === "__ALL__";
    setRegisterAllSchemas(isAll);
    setSchemaName(isAll ? "" : schema);

    const cleanDbName = (selectedDatabase || "db").toLowerCase().replace(/[^a-z0-9_]/g, "_");
    const cleanSchemaName = schema.toLowerCase().replace(/[^a-z0-9_]/g, "_");

    if (isAll) {
      setDomainId(cleanDbName);
      setDisplayName(`${selectedDatabase.replace(/_/g, " ")} (Tất cả schemas)`);
    } else {
      const isGenericSchema = ["main", "dbo", "public", ""].includes(cleanSchemaName);
      const suggestedDomain = !isGenericSchema && cleanSchemaName
        ? `${cleanDbName}_${cleanSchemaName}`
        : cleanDbName;
      setDomainId(suggestedDomain);
      setDisplayName(
        !isGenericSchema
          ? `${selectedDatabase.replace(/_/g, " ")} - ${schema}`
          : selectedDatabase.replace(/_/g, " ")
      );
    }
  };

  // Bước 3: Hoàn tất kết nối CSDL và Crawl Schema
  const handleConnectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectionUrl.trim()) {
      setError("Vui lòng nhập chuỗi kết nối CSDL (Connection URL hoặc File Path).");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessResult(null);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("jwt_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/domains/connect", {
        method: "POST",
        headers,
        body: JSON.stringify({
          connection_url: connectionUrl.trim(),
          db_name: selectedDatabase || undefined,
          domain_id: domainId.trim() || undefined,
          display_name: displayName.trim() || undefined,
          schema_name: (selectedSchema === "__ALL__" ? undefined : selectedSchema) || schemaName.trim() || undefined,
          save_yaml: saveYaml,
          register_all_schemas: registerAllSchemas || selectedSchema === "__ALL__",
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Lỗi máy chủ (${res.status})`);
      }

      setSuccessResult({
        type: "connect",
        data,
      });

      if (onSuccess) {
        onSuccess(data.domain_id);
      }
    } catch (err: any) {
      setError(err.message || "Không thể kết nối CSDL.");
    } finally {
      setLoading(false);
    }
  };

  // Tab 2: Ingest Data
  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessResult(null);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("jwt_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/domains/${targetDomain}/ingest`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          source_url: ingestSourceUrl.trim() || undefined,
          schema_name: ingestSchema.trim() || undefined,
          mode: syncMode,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Lỗi nạp dữ liệu (${res.status})`);
      }

      setSuccessResult({
        type: "ingest",
        data,
      });

      if (onSuccess) {
        onSuccess(targetDomain);
      }
    } catch (err: any) {
      setError(err.message || "Lỗi khi kích hoạt Ingestion.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-xl rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center shrink-0">
              <Database size={18} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                Quản Trị Dữ Liệu Tự Phục Vụ
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono">
                  Self-Service Onboarding
                </span>
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Tự động khám phá schema, chọn database & schema nạp vào Data Catalog
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-zinc-200 dark:border-zinc-800 px-6 bg-zinc-50/50 dark:bg-zinc-950/20 text-xs">
          <button
            type="button"
            onClick={() => {
              setActiveTab("connect");
              setError(null);
              setSuccessResult(null);
            }}
            className={`py-3 px-4 font-semibold border-b-2 flex items-center gap-2 transition-all ${
              activeTab === "connect"
                ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            <Plus size={14} />
            Kết Nối CSDL & Khám Phá Domain
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab("ingest");
              setError(null);
              setSuccessResult(null);
            }}
            className={`py-3 px-4 font-semibold border-b-2 flex items-center gap-2 transition-all ${
              activeTab === "ingest"
                ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            <RefreshCw size={14} />
            Nạp Dữ Liệu Vào DuckDB (Ingest)
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-start gap-2.5">
              <AlertTriangle size={15} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successResult ? (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 space-y-3 animate-in fade-in">
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold text-xs">
                <CheckCircle2 size={16} />
                <span>
                  {successResult.type === "connect"
                    ? "Đã kết nối và đăng ký Domain thành công!"
                    : "Đã nạp dữ liệu vào DuckDB thành công!"}
                </span>
              </div>

              {successResult.type === "connect" && (
                <div className="text-xs text-zinc-600 dark:text-zinc-300 space-y-1 font-mono">
                  <p>• Mã Domain: <strong>{successResult.data.domain_id}</strong></p>
                  <p>• Tên hiển thị: <strong>{successResult.data.display_name}</strong></p>
                  <p>• Cơ sở dữ liệu: <strong>{successResult.data.database_name}</strong></p>
                  <p>• Schema: <strong>{successResult.data.schema_name}</strong></p>
                  <p>• Số bảng phát hiện: <strong>{successResult.data.tables_count}</strong></p>
                  <p>• Số chỉ số MetricFlow: <strong>{successResult.data.metrics_count}</strong></p>
                  <p>• Quan hệ khoá ngoại (Joins): <strong>{successResult.data.relationships_count}</strong></p>
                </div>
              )}

              {successResult.type === "ingest" && (
                <div className="text-xs text-zinc-600 dark:text-zinc-300 space-y-1 font-mono">
                  <p>• Bảng đồng bộ: <strong>{successResult.data.tables_synced_count ?? successResult.data.total_tables ?? "Toàn bộ"}</strong></p>
                  <p>• Bản ghi đã nạp: <strong>{(successResult.data.total_rows_ingested || successResult.data.rows_ingested || 0).toLocaleString()} dòng</strong></p>
                  <p>• Thời gian: <strong>{successResult.data.duration_sec ?? "< 1"}s</strong></p>
                  <p>• Trạng thái DuckDB: <strong>SUCCESS</strong></p>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors"
                >
                  Hoàn Tất & Đóng
                </button>
              </div>
            </div>
          ) : activeTab === "connect" ? (
            /* TAB 1: CONNECT DATABASE (MULTI-STEP DISCOVERY) */
            <form onSubmit={handleConnectSubmit} className="space-y-4">
              {/* Dialect selector */}
              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5">
                  Hệ quản trị CSDL nguồn
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  {[
                    { id: "postgresql", label: "PostgreSQL" },
                    { id: "mssql", label: "SQL Server" },
                    { id: "mysql", label: "MySQL" },
                    { id: "duckdb", label: "DuckDB / SQLite" },
                  ].map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => handleDialectChange(item.id)}
                      className={`py-2 px-2.5 rounded-xl border text-center font-medium transition-all ${
                        dialect === item.id
                          ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-bold shadow-xs"
                          : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Connection URL Input & Discovery Button */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                    Chuỗi kết nối (Connection URL / File Path) <span className="text-rose-500">*</span>
                  </label>
                  {connectionTested && (
                    <button
                      type="button"
                      onClick={() => {
                        setConnectionTested(false);
                        setInspectMessage(null);
                      }}
                      className="text-[11px] text-[var(--accent-primary)] hover:underline flex items-center gap-1 font-medium"
                    >
                      <RotateCcw size={11} />
                      Đổi kết nối
                    </button>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    value={connectionUrl}
                    onChange={(e) => {
                      setConnectionUrl(e.target.value);
                      if (connectionTested) setConnectionTested(false);
                    }}
                    placeholder="postgresql://user:password@localhost:5432/my_database"
                    className="flex-1 px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                  />
                  {!connectionTested && (
                    <button
                      type="button"
                      disabled={isInspecting || !connectionUrl.trim()}
                      onClick={() => handleInspectConnection()}
                      className="px-3.5 py-2 rounded-xl bg-[var(--accent-primary)] hover:opacity-90 text-[var(--accent-primary-text)] text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50 shrink-0 shadow-xs"
                    >
                      {isInspecting ? (
                        <>
                          <Loader2 size={13} className="animate-spin" />
                          <span>Đang kiểm tra...</span>
                        </>
                      ) : (
                        <>
                          <Search size={13} />
                          <span>Kiểm Tra & Khám Phá</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>

              {/* SUCCESS DISCOVERY BANNER */}
              {connectionTested && inspectMessage && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center justify-between gap-2 animate-in fade-in">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={15} className="shrink-0" />
                    <span className="font-medium">{inspectMessage}</span>
                  </div>
                </div>
              )}

              {/* STEP 2: CHỌN DATABASE & SCHEMA (KHI ĐÃ KIỂM TRA KẾT NỐI THÀNH CÔNG) */}
              {connectionTested && (
                <div className="space-y-4 pt-1 animate-in fade-in slide-in-from-top-2 duration-300">
                  {/* Section: Chọn Cơ Sở Dữ Liệu (Database) */}
                  <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-950/40 space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                        <Database size={13} className="text-blue-500" />
                        <span>1. Chọn Cơ Sở Dữ Liệu (Database)</span>
                      </label>
                      <span className="text-[11px] text-zinc-500 font-mono">
                        {discoveredDatabases.length} CSDL tìm thấy
                      </span>
                    </div>

                    {discoveredDatabases.length > 0 ? (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 max-h-36 overflow-y-auto">
                        {discoveredDatabases.map((db) => {
                          const isSelected = selectedDatabase === db;
                          return (
                            <button
                              type="button"
                              key={db}
                              onClick={() => handleDatabaseChange(db)}
                              className={`p-2 rounded-lg border text-left text-xs transition-all flex items-center justify-between ${
                                isSelected
                                  ? "border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold shadow-xs"
                                  : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                              }`}
                            >
                              <span className="truncate font-mono">{db}</span>
                              {isSelected && <Check size={13} className="shrink-0" />}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={selectedDatabase}
                        onChange={(e) => setSelectedDatabase(e.target.value)}
                        placeholder="Nhập tên CSDL..."
                        className="w-full px-3 py-1.5 text-xs rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-blue-500"
                      />
                    )}
                  </div>

                  {/* Section: Chọn Lược Đồ (Schema) */}
                  <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-950/40 space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                        <Layers size={13} className="text-purple-500" />
                        <span>2. Chọn Lược Đồ Nghiệp Vụ (Schema)</span>
                      </label>
                      <span className="text-[11px] text-zinc-500 font-mono">
                        {discoveredSchemas.length} schemas
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-2 pt-1">
                      {discoveredSchemas.map((sch) => {
                        const isSelected = selectedSchema === sch;
                        return (
                          <button
                            type="button"
                            key={sch}
                            onClick={() => handleSchemaChange(sch)}
                            className={`px-3 py-1.5 rounded-lg border text-xs font-mono transition-all flex items-center gap-1.5 ${
                              isSelected
                                ? "border-purple-500 bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold shadow-xs"
                                : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                            }`}
                          >
                            <span>{sch}</span>
                            {isSelected && <Check size={12} />}
                          </button>
                        );
                      })}

                      {/* Tùy chọn Quét tất cả schemas */}
                      {discoveredSchemas.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleSchemaChange("__ALL__")}
                          className={`px-3 py-1.5 rounded-lg border text-xs transition-all flex items-center gap-1.5 ${
                            selectedSchema === "__ALL__"
                              ? "border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold shadow-xs"
                              : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                          }`}
                        >
                          <Sparkles size={12} className="text-emerald-500" />
                          <span>Tất cả Schemas</span>
                          {selectedSchema === "__ALL__" && <Check size={12} />}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Section: Cấu hình thông tin Domain tạo mới */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                        Mã Domain (Slug) <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={domainId}
                        onChange={(e) => setDomainId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                        placeholder="vd: retail_sales"
                        className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                        Tên hiển thị tiếng Việt
                      </label>
                      <input
                        type="text"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="vd: Bán Lẻ & Chuỗi Cửa Hàng"
                        className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                      />
                    </div>
                  </div>

                  {/* Tùy chọn lưu YAML */}
                  <div className="pt-1">
                    <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={saveYaml}
                        onChange={(e) => setSaveYaml(e.target.checked)}
                        className="rounded text-[var(--accent-primary)]"
                      />
                      <span>Tự động lưu cấu hình YAML vào thư mục domains/</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Form buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  Hủy
                </button>
                {connectionTested ? (
                  <button
                    type="submit"
                    disabled={loading || !selectedDatabase}
                    className="px-4 py-2 rounded-xl bg-[var(--accent-primary)] text-[var(--accent-primary-text)] text-xs font-semibold hover:opacity-90 transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm"
                  >
                    {loading && <Loader2 size={14} className="animate-spin" />}
                    <span>{loading ? "Đang crawl cấu trúc CSDL..." : "Hoàn Tất Kết Nối CSDL"}</span>
                    <ArrowRight size={14} />
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={isInspecting || !connectionUrl.trim()}
                    onClick={() => handleInspectConnection()}
                    className="px-4 py-2 rounded-xl bg-[var(--accent-primary)] text-[var(--accent-primary-text)] text-xs font-semibold hover:opacity-90 transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm"
                  >
                    {isInspecting && <Loader2 size={14} className="animate-spin" />}
                    <span>{isInspecting ? "Đang kiểm tra kết nối..." : "Kiểm Tra & Khám Phá"}</span>
                    <ArrowRight size={14} />
                  </button>
                )}
              </div>
            </form>
          ) : (
            /* TAB 2: INGEST TO DUCKDB */
            <form onSubmit={handleIngestSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  Domain đích để nạp dữ liệu <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={targetDomain}
                  onChange={(e) => setTargetDomain(e.target.value)}
                  placeholder="vd: real_estate, ecommerce..."
                  className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                  URL kết nối nguồn (Để trống nếu dùng mặc định trong .env)
                </label>
                <input
                  type="text"
                  value={ingestSourceUrl}
                  onChange={(e) => setIngestSourceUrl(e.target.value)}
                  placeholder="mssql+pymssql://sa:password@localhost:1433/db hoặc postgresql://..."
                  className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Schema nguồn (Tùy chọn)
                  </label>
                  <input
                    type="text"
                    value={ingestSchema}
                    onChange={(e) => setIngestSchema(e.target.value)}
                    placeholder="dbo, public..."
                    className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-mono focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                    Chế độ nạp (Sync Mode)
                  </label>
                  <select
                    value={syncMode}
                    onChange={(e) => setSyncMode(e.target.value as any)}
                    className="w-full px-3 py-2 text-xs rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                  >
                    <option value="full_refresh">Full Refresh (Xoá nạp lại)</option>
                    <option value="append">Append (Nạp thêm dòng)</option>
                  </select>
                </div>
              </div>

              {/* Form buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm"
                >
                  {loading && <Loader2 size={14} className="animate-spin" />}
                  <span>{loading ? "Đang nạp dữ liệu..." : "Kích Hoạt Nạp Dữ Liệu"}</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
