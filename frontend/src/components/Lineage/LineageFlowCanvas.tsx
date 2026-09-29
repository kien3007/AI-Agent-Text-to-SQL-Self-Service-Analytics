"use client";

import React, { useMemo, useState, useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
  BackgroundVariant
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { LineageGraphData, LineageGraphNode } from "@/types/chat";
import CustomLineageNode from "./CustomLineageNode";
import { Filter, Search, RotateCcw, Maximize2, Layers } from "lucide-react";

const nodeTypes = {
  customLineageNode: CustomLineageNode,
};

interface LineageFlowCanvasProps {
  graphData: LineageGraphData | null;
  onSelectNode: (node: LineageGraphNode | null) => void;
  selectedNodeId?: string | null;
}

const LAYER_X_POSITIONS: Record<string, number> = {
  source: 60,
  staging: 360,
  warehouse: 680,
  metric: 1000,
  consumer: 1320,
};

export default function LineageFlowCanvas({
  graphData,
  onSelectNode,
  selectedNodeId,
}: LineageFlowCanvasProps) {
  const [activeLayerFilter, setActiveLayerFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");

  // Calculate layout and positions for nodes
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!graphData) return { initialNodes: [], initialEdges: [] };

    // Group nodes by layer
    const layerGroups: Record<string, LineageGraphNode[]> = {
      source: [],
      staging: [],
      warehouse: [],
      metric: [],
      consumer: [],
    };

    graphData.nodes.forEach((n) => {
      const l = n.layer || "warehouse";
      if (!layerGroups[l]) layerGroups[l] = [];
      layerGroups[l].push(n);
    });

    const flowNodes: Node[] = [];
    const maxNodes = Math.max(...Object.values(layerGroups).map((g) => g.length), 1);

    Object.entries(layerGroups).forEach(([layer, nodesInLayer]) => {
      const x = LAYER_X_POSITIONS[layer] || 500;
      const count = nodesInLayer.length;
      // Vertically center column nodes relative to the tallest column
      const startY = Math.max(50, ((maxNodes - count) * 130) / 2 + 50);

      nodesInLayer.forEach((n, idx) => {
        const y = startY + idx * 130;
        flowNodes.push({
          id: n.id,
          type: "customLineageNode",
          position: { x, y },
          data: {
            node: n,
          },
          selected: n.id === selectedNodeId,
        });
      });
    });

    const flowEdges: Edge[] = graphData.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      animated: e.animated,
      type: "smoothstep",
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 14,
        height: 14,
        color: "var(--border-medium)",
      },
      style: {
        stroke: "var(--border-medium)",
        strokeWidth: 1.5,
        ...e.style,
      },
      labelStyle: {
        fill: "var(--text-muted)",
        fontSize: 10,
        fontFamily: "monospace",
      },
      labelBgStyle: {
        fill: "var(--bg-app)",
        fillOpacity: 0.85,
      },
    }));

    return { initialNodes: flowNodes, initialEdges: flowEdges };
  }, [graphData, selectedNodeId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state when initial data updates
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Handle node selection
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const rawNode = (node.data as any)?.node as LineageGraphNode;
      onSelectNode(rawNode || null);
    },
    [onSelectNode]
  );

  const handlePaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  // Apply filters / highlighting
  const filteredNodes = useMemo(() => {
    return nodes.map((n) => {
      const rawNode = (n.data as any)?.node as LineageGraphNode;
      const matchesLayer =
        activeLayerFilter === "all" || rawNode.layer === activeLayerFilter;
      const matchesSearch =
        !searchTerm.trim() ||
        rawNode.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (rawNode.vn_label &&
          rawNode.vn_label.toLowerCase().includes(searchTerm.toLowerCase()));

      const isDimmed = !matchesLayer || !matchesSearch;

      return {
        ...n,
        style: {
          ...n.style,
          opacity: isDimmed ? 0.25 : 1,
          pointerEvents: (isDimmed ? "none" : "auto") as React.CSSProperties["pointerEvents"],
          transition: "opacity 0.2s ease",
        },
      };
    });
  }, [nodes, activeLayerFilter, searchTerm]);

  return (
    <div className="relative w-full h-[620px] min-h-[620px] shrink-0 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs overflow-hidden flex flex-col">
      {/* Top Toolbar */}
      <div className="shrink-0 p-3 border-b border-[var(--border-subtle)] bg-[var(--bg-app)]/60 backdrop-blur-xs flex flex-wrap items-center justify-between gap-3 z-10">
        {/* Layer Filters */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3" /> Tầng:
          </span>
          {[
            { id: "all", label: "Tất Cả" },
            { id: "source", label: "Nguồn (Raw)" },
            { id: "staging", label: "Staging" },
            { id: "warehouse", label: "Warehouse Tables" },
            { id: "metric", label: "Metrics" },
            { id: "consumer", label: "Consumers" },
          ].map((l) => (
            <button
              key={l.id}
              onClick={() => setActiveLayerFilter(l.id)}
              className={`shrink-0 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                activeLayerFilter === l.id
                  ? "bg-purple-600 text-white shadow-xs"
                  : "bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        {/* Search in DAG */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Tìm kiếm node trên sơ đồ..."
            className="pl-8 pr-3 py-1.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:border-purple-500 w-56"
          />
        </div>
      </div>

      {/* Main Graph Area */}
      <div className="flex-1 w-full h-full relative">
        <ReactFlow
          nodes={filteredNodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15, minZoom: 0.7, maxZoom: 1.1 }}
          minZoom={0.3}
          maxZoom={1.8}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={24}
            size={1.5}
            color="var(--border-medium)"
          />
          <Controls
            showInteractive={false}
            className="!bg-[var(--bg-card)] !border !border-[var(--border-subtle)] !rounded-xl !shadow-xs overflow-hidden"
          />
          <MiniMap
            nodeStrokeWidth={3}
            nodeColor={(n: any) => {
              const layer = n.data?.node?.layer;
              if (layer === "source") return "#f59e0b";
              if (layer === "staging") return "#0ea5e9";
              if (layer === "warehouse") return "#a855f7";
              if (layer === "metric") return "#10b981";
              return "#f43f5e";
            }}
            className="!bg-[var(--bg-card)] !border !border-[var(--border-subtle)] !rounded-xl !shadow-xs overflow-hidden"
          />
        </ReactFlow>
      </div>

      {/* Bottom Hint */}
      <div className="shrink-0 px-4 py-2 border-t border-[var(--border-subtle)] bg-[var(--bg-app)]/40 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
        <span>Kéo để di chuyển • Cuộn chuột để zoom • Nhấp vào node để xem chi tiết & phân tích tác động</span>
        <span className="font-mono">
          {graphData?.nodes.length || 0} nodes • {graphData?.edges.length || 0} edges
        </span>
      </div>
    </div>
  );
}
