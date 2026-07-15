/**
 * RoleHierarchyTree
 *
 * Renders the role hierarchy as an interactive React Flow graph,
 * laid out top-down using Dagre.
 */
import React, { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  type Node,
  type Edge,
  BackgroundVariant,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import type { RoleTreeNode } from "../../types/admin";
import { Users, Crown, Shield } from "lucide-react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_WIDTH = 210;
const NODE_HEIGHT = 76;

// ---------------------------------------------------------------------------
// Custom Node
// ---------------------------------------------------------------------------

interface CustomRoleNodeData {
  name: string;
  descendant_count: number;
  is_admin: boolean;
  is_default: boolean;
  [key: string]: unknown; // satisfies React Flow's Record<string, unknown>
}

function CustomRoleNode({ data }: { data: CustomRoleNodeData }) {
  const { name, descendant_count, is_admin, is_default } = data;

  const badgeEl = is_admin ? (
    <span className="inline-flex items-center bg-indigo-100 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300 rounded-full px-2 py-1 text-[10px] font-semibold">
      <Crown className="w-2.5 h-2.5 pb-0.5" /> Admin
    </span>
  ) : is_default ? (
    <span className="inline-flex items-center gap-1 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-full px-2 py-0.5 text-[10px] font-semibold">
      <Shield className="w-2.5 h-2.5" /> Default
    </span>
  ) : null;

  return (
    <>
      {/* Target handle — top centre (incoming edge from parent) */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: "#6366f1",
          width: 8,
          height: 8,
          border: "2px solid white",
        }}
      />

      <div
        className="
          relative group
          bg-white dark:bg-slate-900
          border border-slate-200 dark:border-slate-700
          hover:border-indigo-400 dark:hover:border-indigo-500
          rounded-xl shadow-sm hover:shadow-md
          transition-all duration-200
          flex flex-col justify-center
          px-4 py-2.5
          cursor-default select-none
        "
        style={{ width: NODE_WIDTH, minHeight: NODE_HEIGHT }}
      >
        {/* Left accent bar */}
        <div className="absolute left-0 top-3 bottom-3 w-1 rounded-r-full bg-indigo-500 dark:bg-indigo-400 opacity-70 group-hover:opacity-100 transition-opacity" />

        {/* Role name */}
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 leading-tight truncate pl-1">
          {name}
          <span className="ml-2 py-1">{badgeEl}</span>
        </p>

        {/* Badge + descendant count row */}

        <div className="flex items-center gap-2 mt-1.5 pl-1">
          {descendant_count > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400 dark:text-slate-500">
              <Users className="w-3 h-3" />
              {descendant_count} sub-role{descendant_count !== 1 ? "s" : ""}
            </span>
          )}
          {descendant_count === 0 && !badgeEl && (
            <span className="text-[11px] text-slate-400 dark:text-slate-600 italic">
              leaf role
            </span>
          )}
        </div>
      </div>

      {/* Source handle — bottom centre (outgoing edge to children) */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: "#6366f1",
          width: 8,
          height: 8,
          border: "2px solid white",
        }}
      />
    </>
  );
}

const nodeTypes = { roleNode: CustomRoleNode };

// ---------------------------------------------------------------------------
// Dagre layout helper
// ---------------------------------------------------------------------------

function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 48, ranksep: 72 });

  nodes.forEach((n) =>
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }),
  );
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  const laidOutNodes: Node[] = nodes.map((n) => {
    const { x, y } = g.node(n.id);
    return {
      ...n,
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
      targetPosition: Position.Top,
      sourcePosition: Position.Bottom,
    };
  });

  return { nodes: laidOutNodes, edges };
}

// ---------------------------------------------------------------------------
// Tree → flat nodes + edges
// ---------------------------------------------------------------------------

function flattenTree(
  nodes: RoleTreeNode[],
  result: { rfNodes: Node[]; rfEdges: Edge[] } = { rfNodes: [], rfEdges: [] },
): { rfNodes: Node[]; rfEdges: Edge[] } {
  for (const node of nodes) {
    result.rfNodes.push({
      id: node.id,
      type: "roleNode",
      position: { x: 0, y: 0 }, // overwritten by Dagre
      data: {
        name: node.name,
        descendant_count: node.descendant_count,
        is_admin: node.is_admin,
        is_default: node.is_default,
      } as CustomRoleNodeData,
    });

    if (node.parent_role_id) {
      result.rfEdges.push({
        id: `e-${node.parent_role_id}-${node.id}`,
        source: node.parent_role_id,
        target: node.id,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#6366f1", strokeWidth: 1.5 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#6366f1",
          width: 16,
          height: 16,
        },
      });
    }

    if (node.children.length > 0) {
      flattenTree(node.children, result);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  treeData: RoleTreeNode[];
  isLoading: boolean;
  isError: boolean;
}

export const RoleHierarchyTree: React.FC<Props> = ({
  treeData,
  isLoading,
  isError,
}) => {
  const { nodes, edges } = useMemo(() => {
    if (!treeData || treeData.length === 0) return { nodes: [], edges: [] };
    const { rfNodes, rfEdges } = flattenTree(treeData);
    return applyDagreLayout(rfNodes, rfEdges);
  }, [treeData]);

  // Prevent ReactFlow "onNodesChange" prop warning for read-only usage
  const onNodesChange = useCallback(() => {}, []);
  const onEdgesChange = useCallback(() => {}, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-80">
        <div className="w-8 h-8 rounded-full border-4 border-indigo-200 dark:border-indigo-950 border-t-indigo-700 dark:border-t-indigo-500 animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-80 text-red-500 dark:text-red-400 text-sm">
        Failed to load hierarchy. Please try again.
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-3 text-slate-400 dark:text-slate-500">
        <Users className="w-12 h-12 opacity-30" />
        <p className="text-sm font-medium">No roles to display</p>
      </div>
    );
  }

  return (
    <div
      className="w-full rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden bg-slate-50 dark:bg-slate-950"
      style={{ height: 560 }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="currentColor"
          className="text-slate-200 dark:text-slate-800"
        />
        <Controls
          showInteractive={false}
          className="[&>button]:bg-white [&>button]:dark:bg-slate-900 [&>button]:border-slate-200 [&>button]:dark:border-slate-700 [&>button]:text-slate-600 [&>button]:dark:text-slate-300"
        />
        <MiniMap
          nodeColor={() => "#6366f1"}
          maskColor="rgba(15,23,42,0.08)"
          className="!bg-white dark:!bg-slate-900 !border !border-slate-200 dark:!border-slate-700 !rounded-xl overflow-hidden"
        />
      </ReactFlow>
    </div>
  );
};
