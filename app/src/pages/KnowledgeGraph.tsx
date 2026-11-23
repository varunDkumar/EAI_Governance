import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { DocumentDetail, GraphBuildStatus, GraphNodeDetail, GraphOverview, GraphSourceDocument } from "../lib/types";

const PUBLIC_MODE = import.meta.env.VITE_PUBLIC_MODE === "true";

const COLORS: Record<string, string> = {
  concept: "#45b8e9", framework: "#a879e8", case: "#e9ad37", company: "#24bd91",
  document: "#9aa3b2", agent: "#8795a8", conversation: "#34bfd2", memory: "#9577de", decision: "#df718f",
};
const DOMAIN_TYPES = ["concept", "framework", "case", "company"];
const DOMAIN_RELATIONS = new Set(["RELATED_TO", "ILLUSTRATES", "STUDIES"]);
const EVIDENCE_RELATIONS = new Set(["CONTAINS", "SOURCED_FROM", "DISCUSSES"]);
const OVERVIEW_CORE_LIMIT = 18;
const OVERVIEW_SUBJECT_LIMIT = 5;
const OVERVIEW_SUBJECT_TERMS = [
  ["economics", "econometrics", "economic growth", "gross domestic product", "gdp", "aggregate supply", "monetary and fiscal policy", "demand forecasting", "unit economics"],
  ["marketing", "customer segmentation", "customer profiling", "brand", "market research", "market share", "product attribute", "product development", "product line", "consumer value", "marketing campaign", "willingness-to-pay"],
  ["financial analysis", "behavioral finance", "asset pricing", "capital market", "stock valuation", "investment", "capital structure", "derivatives", "portfolio", "cost of equity", "revenue recognition", "accrual accounting", "cash accounting"],
  ["pricing", "price discrimination", "premium pricing", "willingness to pay", "reservation price", "consumer surplus", "discount utilization", "cost classification", "cost of goods sold", "activity-based costing", "fixed cost", "variable cost"],
];
const LOCAL_NEIGHBOR_LIMIT = 20;
const BACKEND_ORIGIN = API_BASE;
type Point = { x: number; y: number; vx: number; vy: number };
type View = { x: number; y: number; scale: number };

function endpointId(value: string | { id: string }) { return typeof value === "string" ? value : value.id; }
function readableRelation(value: string) { return value.replaceAll("_", " ").toLowerCase(); }
function nodeRadius(degree: number) { return Math.min(16, 5 + Math.sqrt(degree) * 1.8); }
function fittedView(points: Record<string, Point>, width: number, height: number, maxScale = 1.15): View {
  const values = Object.values(points);
  if (!values.length || !width || !height) return { x: width / 2, y: height / 2, scale: 0.8 };
  const minX = Math.min(...values.map((point) => point.x)), maxX = Math.max(...values.map((point) => point.x));
  const minY = Math.min(...values.map((point) => point.y)), maxY = Math.max(...values.map((point) => point.y));
  const graphWidth = Math.max(1, maxX - minX), graphHeight = Math.max(1, maxY - minY);
  const scale = Math.max(0.18, Math.min(maxScale, (width - 120) / graphWidth, (height - 100) / graphHeight));
  return { x: width / 2 - ((minX + maxX) / 2) * scale, y: height / 2 - ((minY + maxY) / 2) * scale, scale };
}
function clusteredSeeds(nodes: GraphOverview["nodes"], edges: GraphOverview["edges"]): Record<string, Point> {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const neighbors = new Map(nodes.map((node) => [node.id, new Set<string>()]));
  for (const edge of edges) {
    const a = endpointId(edge.source), b = endpointId(edge.target);
    if (!byId.has(a) || !byId.has(b)) continue;
    neighbors.get(a)?.add(b); neighbors.get(b)?.add(a);
  }
  const seen = new Set<string>(), components: string[][] = [];
  for (const node of nodes) {
    if (seen.has(node.id)) continue;
    const stack = [node.id], component: string[] = [];
    seen.add(node.id);
    while (stack.length) {
      const id = stack.pop()!; component.push(id);
      for (const next of neighbors.get(id) ?? []) if (!seen.has(next)) { seen.add(next); stack.push(next); }
    }
    components.push(component);
  }
  components.sort((a, b) => b.length - a.length || (byId.get(a[0])?.label ?? "").localeCompare(byId.get(b[0])?.label ?? ""));
  const columns = Math.max(1, Math.ceil(Math.sqrt(components.length))), rows = Math.ceil(components.length / columns);
  const cellWidth = 460, cellHeight = 400, centerX = (columns - 1) * cellWidth / 2, centerY = (rows - 1) * cellHeight / 2;
  const positions: Record<string, Point> = {};
  components.forEach((component, componentIndex) => {
    const column = componentIndex % columns, row = Math.floor(componentIndex / columns);
    const cx = column * cellWidth - centerX, cy = row * cellHeight - centerY;
    const radius = Math.min(118, 38 + Math.sqrt(component.length) * 28);
    component.forEach((id, index) => {
      const angle = component.length === 1 ? 0 : -Math.PI / 2 + index * 2 * Math.PI / component.length;
      positions[id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, vx: 0, vy: 0 };
    });
  });
  return positions;
}

export default function KnowledgeGraph() {
  const [overview, setOverview] = useState<GraphOverview | null>(null);
  const [selected, setSelected] = useState<GraphNodeDetail | null>(null);
  const [sources, setSources] = useState<GraphSourceDocument[]>([]);
  const [sourcesForNode, setSourcesForNode] = useState<string | null>(null);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [viewerDocument, setViewerDocument] = useState<GraphSourceDocument | null>(null);
  const [documentPreview, setDocumentPreview] = useState<DocumentDetail | null>(null);
  const [buildJob, setBuildJob] = useState<GraphBuildStatus | null>(null);
  const [search, setSearch] = useState("");
  const [enabledTypes, setEnabledTypes] = useState<string[]>(DOMAIN_TYPES);
  const [showAllTopics, setShowAllTopics] = useState(false);
  const [localMode, setLocalMode] = useState(false);
  const [includeEvidence, setIncludeEvidence] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, scale: 1 });
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const pollRef = useRef<number | null>(null);
  const pointerRef = useRef<{ x: number; y: number; lastX: number; lastY: number; nodeId: string | null; moved: boolean } | null>(null);
  const initialFit = useRef(false);
  const viewRef = useRef(view);
  const positionsRef = useRef(positions);
  const savedGlobalPositions = useRef<Record<string, Point> | null>(null);
  const detailsCache = useRef(new Map<string, GraphNodeDetail>());
  viewRef.current = view;
  positionsRef.current = positions;

  const refresh = useCallback(() => api.get<GraphOverview>("/graph/overview").then(setOverview), []);
  useRetryingEffect(refresh, [refresh]);
  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);
  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const resize = () => setCanvasSize({ width: element.clientWidth, height: element.clientHeight });
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!initialFit.current && canvasSize.width && canvasSize.height) {
      initialFit.current = true;
      setView({ x: canvasSize.width / 2, y: canvasSize.height / 2, scale: 0.8 });
    }
  }, [canvasSize]);

  const nodeById = useMemo(() => new Map((overview?.nodes ?? []).map((node) => [node.id, node])), [overview]);
  const domainNodesAll = useMemo(() => (overview?.nodes ?? []).filter((node) => DOMAIN_TYPES.includes(node.node_type)), [overview]);
  const topicEdges = useMemo(() => (overview?.edges ?? []).filter((edge) => DOMAIN_RELATIONS.has(edge.relation)
    && nodeById.has(endpointId(edge.source)) && nodeById.has(endpointId(edge.target))
    && DOMAIN_TYPES.includes(nodeById.get(endpointId(edge.source))!.node_type)
    && DOMAIN_TYPES.includes(nodeById.get(endpointId(edge.target))!.node_type)), [overview, nodeById]);
  const degree = useMemo(() => {
    const result = new Map<string, number>();
    for (const edge of topicEdges) {
      result.set(endpointId(edge.source), (result.get(endpointId(edge.source)) ?? 0) + 1);
      result.set(endpointId(edge.target), (result.get(endpointId(edge.target)) ?? 0) + 1);
    }
    return result;
  }, [topicEdges]);
  // A node with zero links in the domain-relation graph has no edge that
  // could ever be drawn for it — plotting it just reads as a random
  // disconnected dot. Drop it from the canvas (it's still reachable via search).
  const topicNodes = useMemo(() => domainNodesAll.filter((node) => (degree.get(node.id) ?? 0) > 0), [domainNodesAll, degree]);
  const overviewNodes = useMemo(() => {
    const byDegree = (a: GraphOverview["nodes"][number], b: GraphOverview["nodes"][number]) =>
      (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.label.localeCompare(b.label);
    const core = topicNodes.filter((node) => !/machine learning/i.test(node.label)).sort(byDegree).slice(0, OVERVIEW_CORE_LIMIT);
    const subjectTermSet = OVERVIEW_SUBJECT_TERMS.flat();
    const subjectNodes = OVERVIEW_SUBJECT_TERMS.flatMap((terms) => {
      const seeds = topicNodes
        .filter((node) => terms.some((term) => node.label.toLowerCase().includes(term)))
        .sort(byDegree)
        .slice(0, OVERVIEW_SUBJECT_LIMIT);
      const seedIds = new Set(seeds.map((node) => node.id));
      const neighborIds = new Set<string>();
      for (const edge of topicEdges) {
        const a = endpointId(edge.source), b = endpointId(edge.target);
        if (seedIds.has(a)) neighborIds.add(b);
        if (seedIds.has(b)) neighborIds.add(a);
      }
      const neighbors = [...neighborIds]
        .map((id) => topicNodes.find((node) => node.id === id))
        .filter((node): node is GraphOverview["nodes"][number] => node !== undefined
          && !/machine learning/i.test(node.label)
          && subjectTermSet.some((term) => node.label.toLowerCase().includes(term)))
        .sort(byDegree)
        .slice(0, 4);
      return [...seeds, ...neighbors];
    });
    const shortlist = [...new Map([...core, ...subjectNodes].map((node) => [node.id, node])).values()];
    const shortlistIds = new Set(shortlist.map((node) => node.id)), linked = new Set<string>();
    for (const edge of topicEdges) {
      const a = endpointId(edge.source), b = endpointId(edge.target);
      if (shortlistIds.has(a) && shortlistIds.has(b)) { linked.add(a); linked.add(b); }
    }
    return shortlist.filter((node) => linked.has(node.id));
  }, [topicNodes, topicEdges, degree]);
  const graphNodes = showAllTopics ? topicNodes : overviewNodes;
  const graphNodeIds = useMemo(() => new Set(graphNodes.map((node) => node.id)), [graphNodes]);
  const graphEdges = useMemo(() => topicEdges.filter((edge) => graphNodeIds.has(endpointId(edge.source)) && graphNodeIds.has(endpointId(edge.target))), [topicEdges, graphNodeIds]);
  const priorityLabels = useMemo(() => new Set(
    [...graphNodes].sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)).slice(0, 16).map((node) => node.id),
  ), [graphNodes, degree]);
  // Most of the graph is small, mutually-connected clusters (2-6 nodes) that
  // read as meaningless anonymous dots without their labels — there's no
  // clutter risk labelling a cluster that small, so always show them. Only
  // the few large, dense clusters still rely on hover/priority to stay legible.
  const componentSize = useMemo(() => {
    const neighbors = new Map<string, Set<string>>();
    for (const node of graphNodes) neighbors.set(node.id, new Set());
    for (const edge of graphEdges) {
      const a = endpointId(edge.source), b = endpointId(edge.target);
      neighbors.get(a)?.add(b);
      neighbors.get(b)?.add(a);
    }
    const seen = new Set<string>();
    const sizes = new Map<string, number>();
    for (const node of graphNodes) {
      if (seen.has(node.id)) continue;
      const stack = [node.id];
      const component: string[] = [];
      seen.add(node.id);
      while (stack.length) {
        const id = stack.pop()!;
        component.push(id);
        for (const next of neighbors.get(id) ?? []) if (!seen.has(next)) { seen.add(next); stack.push(next); }
      }
      for (const id of component) sizes.set(id, component.length);
    }
    return sizes;
  }, [graphNodes, graphEdges]);
  const filteredNodes = useMemo(() => graphNodes.filter((node) => enabledTypes.includes(node.node_type)), [graphNodes, enabledTypes]);
  const visibleNodes = useMemo(() => {
    if (!localMode || !selected) return filteredNodes;
    const nearby = new Set([selected.id]);
    const candidates = new Map<string, number>();
    for (const edge of overview?.edges ?? []) {
      const a = endpointId(edge.source), b = endpointId(edge.target);
      if (a === selected.id && (DOMAIN_RELATIONS.has(edge.relation) || includeEvidence && EVIDENCE_RELATIONS.has(edge.relation))) candidates.set(b, (candidates.get(b) ?? 0) + (edge.confidence ?? 1));
      if (b === selected.id && (DOMAIN_RELATIONS.has(edge.relation) || includeEvidence && EVIDENCE_RELATIONS.has(edge.relation))) candidates.set(a, (candidates.get(a) ?? 0) + (edge.confidence ?? 1));
    }
    [...candidates].sort((a, b) => b[1] - a[1] || (degree.get(b[0]) ?? 0) - (degree.get(a[0]) ?? 0)).slice(0, LOCAL_NEIGHBOR_LIMIT).forEach(([id]) => nearby.add(id));
    return (overview?.nodes ?? []).filter((node) => nearby.has(node.id)
      && (enabledTypes.includes(node.node_type) || node.id === selected.id || includeEvidence && node.node_type === "document"));
  }, [localMode, selected, filteredNodes, overview, enabledTypes, includeEvidence, degree]);
  const visibleIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleEdges = useMemo(() => (overview?.edges ?? []).filter((edge) => {
    const a = endpointId(edge.source), b = endpointId(edge.target);
    return visibleIds.has(a) && visibleIds.has(b)
      && (DOMAIN_RELATIONS.has(edge.relation) || includeEvidence && EVIDENCE_RELATIONS.has(edge.relation));
  }), [overview, visibleIds, includeEvidence]);
  const searchResults = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return (overview?.nodes ?? []).filter((node) => node.label.toLowerCase().includes(q)).slice(0, 7);
  }, [overview, search]);

  // Seed stable positions and settle the subject graph with a small force layout.
  // This leaves large document collections in the inspector instead of treating them as graph clutter.
  useEffect(() => {
    if (!graphNodes.length) return;
    const next: Record<string, Point> = {};
    const seeds = clusteredSeeds(graphNodes, graphEdges);
    graphNodes.forEach((node, index) => {
      const old = positionsRef.current[node.id];
      if (old) next[node.id] = { ...old };
      else {
        next[node.id] = seeds[node.id] ?? { x: index * 24, y: 0, vx: 0, vy: 0 };
      }
    });
    setPositions({ ...next });
    if (initialFit.current && canvasSize.width && canvasSize.height) setView(fittedView(next, canvasSize.width, canvasSize.height));
    const activeEdges = graphEdges.map((edge) => [endpointId(edge.source), endpointId(edge.target)] as const);
    let tick = 0;
    let frame = 0;
    const settle = () => {
      for (let step = 0; step < 3 && tick < 210; step += 1, tick += 1) {
        const alpha = 1 - tick / 220;
        for (const [a, b] of activeEdges) {
          const p = next[a], q = next[b]; if (!p || !q) continue;
          let dx = q.x - p.x, dy = q.y - p.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          const pull = (distance - 112) / distance * 0.018 * alpha;
          dx *= pull; dy *= pull; p.vx += dx; p.vy += dy; q.vx -= dx; q.vy -= dy;
        }
        for (let i = 0; i < graphNodes.length; i += 1) {
          const a = next[graphNodes[i].id];
          for (let j = i + 1; j < graphNodes.length; j += 1) {
            const b = next[graphNodes[j].id];
            const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 16;
            const force = 16 / d2 * alpha;
            a.vx += dx * force; a.vy += dy * force; b.vx -= dx * force; b.vy -= dy * force;
          }
        }
        for (const point of Object.values(next)) {
          point.vx += -point.x * 0.004 * alpha; point.vy += -point.y * 0.004 * alpha;
          point.vx *= 0.82; point.vy *= 0.82; point.x += point.vx; point.y += point.vy;
        }
      }
      if (tick < 210) frame = requestAnimationFrame(settle);
      setPositions({ ...next });
      if (initialFit.current && canvasSize.width && canvasSize.height) setView(fittedView(next, canvasSize.width, canvasSize.height));
    };
    frame = requestAnimationFrame(settle);
    return () => cancelAnimationFrame(frame);
  }, [graphNodes, graphEdges, canvasSize.width, canvasSize.height]);

  useEffect(() => {
    if (!localMode) {
      if (savedGlobalPositions.current) {
        positionsRef.current = savedGlobalPositions.current;
        setPositions(savedGlobalPositions.current);
        savedGlobalPositions.current = null;
      }
      return;
    }
    if (!selected || !canvasSize.width || !canvasSize.height) return;
    if (!savedGlobalPositions.current) savedGlobalPositions.current = { ...positionsRef.current };
    const next = { ...savedGlobalPositions.current };
    const anchor = next[selected.id] ?? { x: 0, y: 0, vx: 0, vy: 0 };
    visibleNodes.filter((node) => node.id !== selected.id).forEach((node, index) => {
      const angle = index * 2.399963229728653;
      const radius = 155 + Math.sqrt(index + 1) * 8;
      next[node.id] = { x: anchor.x + Math.cos(angle) * radius, y: anchor.y + Math.sin(angle) * radius, vx: 0, vy: 0 };
    });
    positionsRef.current = next;
    setPositions(next);
    const localPoints = Object.fromEntries(visibleNodes.map((node) => [node.id, next[node.id]]).filter((entry): entry is [string, Point] => Boolean(entry[1])));
    setView(fittedView(localPoints, canvasSize.width, canvasSize.height, 5.5));
  }, [localMode, selected?.id, visibleNodes.length, canvasSize.width, canvasSize.height]);

  useEffect(() => {
    if (!viewerDocument || viewerDocument.file_type.toLowerCase() === "pdf") { setDocumentPreview(null); return; }
    let active = true;
    api.get<DocumentDetail>(`/repository/documents/${encodeURIComponent(viewerDocument.id)}`)
      .then((document) => { if (active) setDocumentPreview(document); })
      .catch(() => { if (active) setDocumentPreview(null); });
    return () => { active = false; };
  }, [viewerDocument]);

  const focusNode = useCallback((id: string) => {
    const point = positionsRef.current[id];
    if (point && canvasSize.width && canvasSize.height) {
      const next = { x: canvasSize.width / 2 - point.x * viewRef.current.scale, y: canvasSize.height / 2 - point.y * viewRef.current.scale, scale: Math.max(1.15, viewRef.current.scale) };
      viewRef.current = next; setView(next);
    }
  }, [canvasSize]);

  const openNode = useCallback(async (id: string) => {
    let detail = detailsCache.current.get(id);
    try {
      if (!detail) {
        detail = await api.get<GraphNodeDetail>(`/graph/nodes/${encodeURIComponent(id)}`);
        detailsCache.current.set(id, detail);
      }
      setSelected(detail);
      setSources([]); setSourcesForNode(id); setSourcesLoading(true);
      const result = await api.get<{ documents: GraphSourceDocument[] }>(`/graph/nodes/${encodeURIComponent(id)}/sources`);
      setSources(result.documents); setSourcesForNode(id);
      if (result.documents.length === 1) setViewerDocument(result.documents[0]);
    } catch { setSources([]); setSourcesForNode(id); }
    finally { setSourcesLoading(false); }
  }, []);



  function startBuild() {
    api.post<{ job_id: string }>("/graph/build").then(({ job_id }) => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(async () => {
        const status = await api.get<GraphBuildStatus>(`/graph/build/status/${job_id}`);
        setBuildJob(status);
        if (status.status === "done") { if (pollRef.current) window.clearInterval(pollRef.current); pollRef.current = null; detailsCache.current.clear(); await refresh(); }
      }, 1500);
    });
  }

  function chooseResult(id: string) {
    const isTopic = DOMAIN_TYPES.includes(nodeById.get(id)?.node_type ?? "");
    setSearch(""); setSelected(null); setLocalMode(true); setIncludeEvidence(!isTopic);
    void openNode(id); focusNode(id);
  }
  function toggleType(type: string) { setEnabledTypes((current) => current.includes(type) ? current.filter((entry) => entry !== type) : [...current, type]); }
  function changeTopicScope(allTopics: boolean) {
    if (allTopics === showAllTopics) return;
    positionsRef.current = {};
    setPositions({});
    savedGlobalPositions.current = null;
    setSelected(null);
    setHovered(null);
    setShowAllTopics(allTopics);
  }
  function zoomBy(factor: number) { setView((current) => ({ ...current, scale: Math.max(0.35, Math.min(3.5, current.scale * factor)) })); }
  function fitView() {
    initialFit.current = true;
    const visible = Object.fromEntries(visibleNodes.map((node) => [node.id, positionsRef.current[node.id]]).filter((entry): entry is [string, Point] => Boolean(entry[1])));
    setView(fittedView(visible, canvasSize.width, canvasSize.height));
  }
  function returnToFullGraph() {
    setLocalMode(false); setIncludeEvidence(false); setSelected(null);
    const base = savedGlobalPositions.current ?? positionsRef.current;
    if (savedGlobalPositions.current) {
      positionsRef.current = savedGlobalPositions.current;
      setPositions(savedGlobalPositions.current);
      savedGlobalPositions.current = null;
    }
    const allPoints = Object.fromEntries(graphNodes.map((node) => [node.id, base[node.id]]).filter((entry): entry is [string, Point] => Boolean(entry[1])));
    setView(fittedView(allPoints, canvasSize.width, canvasSize.height));
  }
  function clearSelection() {
    if (localMode) returnToFullGraph();
    else setSelected(null);
    setHovered(null);
    setSources([]);
    setSourcesForNode(null);
    setSourcesLoading(false);
    setViewerDocument(null);
    setDocumentPreview(null);
  }
  function canvasPoint(event: React.PointerEvent<SVGSVGElement>) { const rect = event.currentTarget.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; }
  function hitNode(x: number, y: number) {
    const current = viewRef.current;
    for (let i = visibleNodes.length - 1; i >= 0; i -= 1) {
      const node = visibleNodes[i], p = positionsRef.current[node.id]; if (!p) continue;
      if (Math.hypot(x - (p.x * current.scale + current.x), y - (p.y * current.scale + current.y)) <= Math.max(10, nodeRadius(degree.get(node.id) ?? 0) * current.scale + 4)) return node.id;
    }
    return null;
  }

  // React 17+ registers wheel listeners as passive by default, which makes
  // event.preventDefault() in an onWheel JSX prop silently fail — the page
  // scrolls instead of the graph zooming. A native listener can opt out.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const mouseX = event.clientX - rect.left, mouseY = event.clientY - rect.top;
      setView((current) => {
        const scale = Math.max(0.35, Math.min(3.5, current.scale * (event.deltaY < 0 ? 1.12 : 0.89)));
        const ratio = scale / current.scale;
        return { scale, x: mouseX - (mouseX - current.x) * ratio, y: mouseY - (mouseY - current.y) * ratio };
      });
    };
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [overview, visibleNodes.length === 0]);

  const graphStats = overview ? `${visibleNodes.length.toLocaleString()} entities · ${visibleEdges.length.toLocaleString()} links · ${localMode ? "Nearby links" : showAllTopics ? "All linked topics" : "Overview of key linked topics"}` : "Loading graph…";
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Knowledge Graph</h1>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{graphStats} · {overview?.stats.node_count.toLocaleString() ?? "—"} total repository nodes</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <input className="w-64 rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }} placeholder="Find a topic or source…" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && searchResults[0] && chooseResult(searchResults[0].id)} />
            {searchResults.length > 0 && <div className="absolute right-0 top-full z-20 mt-1 max-h-72 w-80 overflow-auto rounded-lg border p-1 shadow-xl" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>{searchResults.map((node) => <button key={node.id} onClick={() => chooseResult(node.id)} className="flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-xs hover:bg-[var(--color-bg)]"><span className="truncate font-medium">{node.label}</span><span className="shrink-0" style={{ color: COLORS[node.node_type] }}>{node.node_type}</span></button>)}</div>}
          </div>
          {!PUBLIC_MODE && <button className="rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ background: "var(--color-primary)" }} onClick={startBuild} disabled={buildJob?.status === "running"}>{buildJob?.status === "running" ? `Building ${buildJob.processed}/${buildJob.total}` : "Rebuild graph"}</button>}
        </div>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {!localMode && <div className="inline-flex rounded-lg border p-0.5" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}><button aria-pressed={!showAllTopics} onClick={() => changeTopicScope(false)} className="rounded-md px-2.5 py-1.5 text-xs" style={{ background: !showAllTopics ? "color-mix(in srgb, var(--color-primary) 12%, transparent)" : "transparent", color: !showAllTopics ? "var(--color-primary)" : "var(--color-text-muted)" }}>Overview · {overviewNodes.length}</button><button aria-pressed={showAllTopics} onClick={() => changeTopicScope(true)} className="rounded-md px-2.5 py-1.5 text-xs" style={{ background: showAllTopics ? "color-mix(in srgb, var(--color-primary) 12%, transparent)" : "transparent", color: showAllTopics ? "var(--color-primary)" : "var(--color-text-muted)" }}>All topics · {topicNodes.length}</button></div>}
          <div className="flex flex-wrap items-center gap-1.5">{DOMAIN_TYPES.map((type) => <button key={type} aria-pressed={enabledTypes.includes(type)} onClick={() => toggleType(type)} className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs" style={{ borderColor: enabledTypes.includes(type) ? `${COLORS[type]}77` : "var(--color-border)", opacity: enabledTypes.includes(type) ? 1 : 0.5, background: "var(--color-surface)" }}><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[type] }} />{type}<span style={{ color: "var(--color-text-muted)" }}>{topicNodes.filter((node) => node.node_type === type).length}</span></button>)}</div>
        </div>
        <div className="flex items-center gap-2">
          {localMode ? <button className="rounded-md border px-2.5 py-1.5 text-xs" style={{ borderColor: "var(--color-border)", color: "var(--color-primary)" }} onClick={returnToFullGraph}>Back to overview</button> : <button className="rounded-md border px-2.5 py-1.5 text-xs" style={{ borderColor: "var(--color-border)", background: selected ? "color-mix(in srgb, var(--color-primary) 12%, transparent)" : "var(--color-surface)", color: selected ? "var(--color-primary)" : "var(--color-text-muted)" }} onClick={() => selected && setLocalMode(true)} disabled={!selected}>Local graph</button>}
          {localMode && <label className="flex items-center gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}><input type="checkbox" checked={includeEvidence} onChange={(event) => setIncludeEvidence(event.target.checked)} />Include documents</label>}
          <button aria-label="Zoom out" className="h-8 w-8 rounded-md border text-sm" style={{ borderColor: "var(--color-border)" }} onClick={() => zoomBy(0.8)}>−</button>
          <button aria-label="Zoom in" className="h-8 w-8 rounded-md border text-sm" style={{ borderColor: "var(--color-border)" }} onClick={() => zoomBy(1.25)}>+</button>
          <button className="rounded-md border px-2.5 py-1.5 text-xs" style={{ borderColor: "var(--color-border)" }} onClick={fitView}>Fit graph</button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-3">
        <div ref={wrapRef} className="relative min-w-0 flex-1 overflow-hidden rounded-xl border" style={{ borderColor: "var(--color-border)", background: "#fbfbfd" }}>
          {!overview ? <div className="flex h-full items-center justify-center text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to graph…</div> : visibleNodes.length === 0 ? <div className="flex h-full items-center justify-center text-sm" style={{ color: "var(--color-text-muted)" }}>No linked topics match these filters.</div> : <svg ref={svgRef} className="h-full w-full touch-none" viewBox={`0 0 ${canvasSize.width} ${canvasSize.height}`} onPointerDown={(event) => { const point = canvasPoint(event); pointerRef.current = { ...point, lastX: point.x, lastY: point.y, nodeId: hitNode(point.x, point.y), moved: false }; event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={(event) => { const point = canvasPoint(event), drag = pointerRef.current; if (drag) { const dx = point.x - drag.lastX, dy = point.y - drag.lastY; if (Math.abs(point.x - drag.x) + Math.abs(point.y - drag.y) > 3) drag.moved = true; drag.lastX = point.x; drag.lastY = point.y; if (drag.moved) { if (drag.nodeId && positionsRef.current[drag.nodeId]) { const p = positionsRef.current[drag.nodeId]; const next = { ...positionsRef.current, [drag.nodeId]: { ...p, x: p.x + dx / viewRef.current.scale, y: p.y + dy / viewRef.current.scale } }; positionsRef.current = next; setPositions(next); } else setView((current) => ({ ...current, x: current.x + dx, y: current.y + dy })); } } else setHovered(hitNode(point.x, point.y)); }} onPointerUp={() => { const drag = pointerRef.current; pointerRef.current = null; if (!drag || drag.moved) return; if (!drag.nodeId) { if (selected) clearSelection(); return; } if (selected?.id === drag.nodeId) { clearSelection(); return; } void openNode(drag.nodeId); focusNode(drag.nodeId); }} onPointerCancel={() => { pointerRef.current = null; }}><g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>{visibleEdges.map((edge) => { const aId = endpointId(edge.source), bId = endpointId(edge.target), a = positions[aId], b = positions[bId]; if (!a || !b) return null; const hot = hovered ? aId === hovered || bId === hovered : selected?.id === aId || selected?.id === bId; const midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2; return <g key={edge.id} opacity={hovered || selected ? hot ? 1 : 0.12 : 0.42}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} onPointerEnter={() => setHoveredEdge(edge.id)} onPointerLeave={() => setHoveredEdge(null)} stroke={hot ? "#6d55c7" : edge.relation === "RELATED_TO" ? "#aeb6c2" : "#7aa8ba"} strokeWidth={hot ? 1.8 : 0.9} markerEnd={edge.relation === "RELATED_TO" ? undefined : "url(#kg-arrow)"} />{hoveredEdge === edge.id && <text x={midX} y={midY} textAnchor="middle" fontSize={12 / view.scale} fill="#62558e" paintOrder="stroke" stroke="#fbfbfd" strokeWidth={4 / view.scale}>{readableRelation(edge.relation)}</text>}</g>; })}<defs><marker id="kg-arrow" viewBox="0 -4 8 8" refX="13" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,-4L8,0L0,4" fill="#7aa8ba" /></marker></defs>{visibleNodes.map((node) => { const point = positions[node.id]; if (!point) return null; const isActive = node.id === hovered || node.id === selected?.id, linked = !hovered && !selected || node.id === hovered || visibleEdges.some((edge) => (endpointId(edge.source) === (hovered ?? selected?.id) || endpointId(edge.target) === (hovered ?? selected?.id)) && (endpointId(edge.source) === node.id || endpointId(edge.target) === node.id)); const radius = nodeRadius(degree.get(node.id) ?? 0); const showLabel = localMode || !showAllTopics || view.scale > 1 || isActive || priorityLabels.has(node.id) || (componentSize.get(node.id) ?? 1) <= 6; return <g key={node.id} opacity={linked ? 1 : 0.17} onPointerEnter={() => setHovered(node.id)} onPointerLeave={() => setHovered(null)} className="cursor-pointer"><title>{node.label}</title><circle cx={point.x} cy={point.y} r={radius} fill={COLORS[node.node_type] ?? COLORS.document} stroke={isActive ? "#403486" : "#ffffff"} strokeWidth={isActive ? 3 / view.scale : 1.5 / view.scale} /><circle cx={point.x} cy={point.y} r={Math.max(12, radius + 5)} fill="transparent" />{showLabel && <text x={point.x + radius + 5} y={point.y + 3} fontSize={(isActive ? 11 : 8) / view.scale} fill={isActive ? "#30284f" : "#454255"} paintOrder="stroke" stroke="#fbfbfd" strokeWidth={3 / view.scale}>{node.label.length > 40 ? `${node.label.slice(0, 37)}…` : node.label}</text>}</g>; })}</g></svg>}
          <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border px-3 py-2 text-[11px] shadow-sm" style={{ borderColor: "var(--color-border)", background: "rgba(255,255,255,.94)", color: "var(--color-text-muted)" }}>Drag to pan · drag a node to rearrange · scroll to zoom · select a node to trace its links</div>
          {localMode && <button className="absolute right-3 top-3 rounded-lg border px-3 py-2 text-xs shadow-sm" style={{ borderColor: "var(--color-border)", background: "rgba(255,255,255,.94)" }} onClick={returnToFullGraph}>← Full graph</button>}
        </div>
        {selected && <aside className="w-80 shrink-0 overflow-y-auto rounded-xl border p-4" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
          <div className="flex items-start justify-between gap-2"><span className="rounded-full px-2 py-1 text-[11px] font-medium text-white" style={{ background: COLORS[selected.node_type] ?? COLORS.document }}>{selected.node_type}</span><button aria-label="Close details" className="text-sm" style={{ color: "var(--color-text-muted)" }} onClick={clearSelection}>×</button></div>
          <h2 className="mt-3 text-base font-semibold leading-snug">{selected.label}</h2>
          {Object.entries(selected.properties ?? {}).filter(([, value]) => ["description", "subtopic", "summary"].includes(String(value))).length === 0 && <p className="mt-2 text-xs" style={{ color: "var(--color-text-muted)" }}>{String(selected.properties?.description ?? selected.properties?.summary ?? "Select a connection below to follow the graph.")}</p>}
          {Object.entries(selected.properties ?? {}).filter(([key, value]) => !["document_id", "memory_id"].includes(key) && ["string", "number", "boolean"].includes(typeof value)).slice(0, 8).map(([key, value]) => <div key={key} className="mt-2 text-xs"><span className="capitalize" style={{ color: "var(--color-text-muted)" }}>{key.replaceAll("_", " ")}</span><p className="mt-0.5 break-words">{String(value)}</p></div>)}
          <section className="mt-5">
            <div className="flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>Source documents</h3><span className="rounded-full px-2 py-0.5 text-[11px]" style={{ background: "var(--color-bg)" }}>{sourcesForNode === selected.id ? sources.length : "—"}</span></div>
            {sourcesLoading && sourcesForNode === selected.id ? <p className="py-3 text-xs" style={{ color: "var(--color-text-muted)" }}>Finding source files…</p> : sourcesForNode !== selected.id || sources.length === 0 ? <p className="py-3 text-xs" style={{ color: "var(--color-text-muted)" }}>No source files are linked to this node.</p> : <div className="mt-2 divide-y" style={{ borderColor: "var(--color-border)" }}>{sources.map((document) => <button key={document.id} onClick={() => setViewerDocument(document)} className="group flex w-full items-start justify-between gap-3 py-2.5 text-left"><span className="min-w-0"><span className="block truncate text-xs font-medium text-[var(--color-primary)] underline decoration-[var(--color-border)] underline-offset-2 group-hover:decoration-current">{document.title}</span><span className="mt-1 block truncate text-[10px]" style={{ color: "var(--color-text-muted)" }}>{[document.course, document.term].filter(Boolean).join(" · ") || document.file_type.toUpperCase()}</span></span><span className="shrink-0 rounded-md border px-2 py-1 text-[10px]" style={{ borderColor: "var(--color-border)" }}>Open</span></button>)}</div>}
          </section>
          <div className="mt-5 flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>Connected notes</h3><span className="rounded-full px-2 py-0.5 text-[11px]" style={{ background: "var(--color-bg)" }}>{selected.connections.length}</span></div>
          <div className="mt-2 divide-y" style={{ borderColor: "var(--color-border)" }}>{selected.connections.map((connection) => <button key={connection.edge_id} onClick={() => { void openNode(connection.node.id); focusNode(connection.node.id); }} className="group block w-full py-3 text-left"><span className="block text-xs font-medium text-[var(--color-primary)] underline decoration-[var(--color-border)] underline-offset-2 group-hover:decoration-current">{connection.node.label}</span><span className="mt-1 block text-[11px] capitalize" style={{ color: "var(--color-text-muted)" }}>{connection.direction === "outgoing" ? "this node" : connection.node.label} {readableRelation(connection.relation)} {connection.direction === "outgoing" ? connection.node.label : "this node"}</span><span className="mt-1 block text-[10px]" style={{ color: COLORS[connection.node.node_type] }}>{connection.node.node_type}</span></button>)}{selected.connections.length === 0 && <p className="py-4 text-xs" style={{ color: "var(--color-text-muted)" }}>No linked notes found.</p>}</div>
        </aside>}
      </div>
      <footer className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>{DOMAIN_TYPES.map((type) => <span key={type} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[type] }} />{type}</span>)}<span className="ml-auto">Node size shows connection count · select to reveal relationship labels</span></footer>
      {viewerDocument && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4" onClick={() => setViewerDocument(null)}><section className="flex h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-xl border bg-white shadow-2xl" style={{ borderColor: "var(--color-border)" }} onClick={(event) => event.stopPropagation()}><header className="flex items-center justify-between gap-4 border-b px-5 py-3" style={{ borderColor: "var(--color-border)" }}><div className="min-w-0"><h2 className="truncate text-sm font-semibold">{viewerDocument.title}</h2><p className="mt-0.5 truncate text-xs" style={{ color: "var(--color-text-muted)" }}>{[viewerDocument.course, viewerDocument.term, viewerDocument.page_count ? `${viewerDocument.page_count} pages` : null].filter(Boolean).join(" · ")}</p></div><button onClick={() => setViewerDocument(null)} className="shrink-0 rounded-md border px-3 py-1.5 text-xs" style={{ borderColor: "var(--color-border)" }}>Close viewer</button></header>{viewerDocument.file_type.toLowerCase() === "pdf" && viewerDocument.file_url ? <iframe title={`PDF: ${viewerDocument.title}`} className="min-h-0 flex-1 bg-slate-100" src={`${BACKEND_ORIGIN}${viewerDocument.file_url}#toolbar=1&navpanes=0`} /> : <div className="min-h-0 flex-1 overflow-y-auto p-6">{!documentPreview ? <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Loading extracted notes…</p> : <div className="mx-auto max-w-3xl space-y-4">{documentPreview.chunks.map((chunk) => <article key={chunk.chunk_index} className="rounded-lg border p-4" style={{ borderColor: "var(--color-border)" }}><p className="mb-2 text-xs font-semibold" style={{ color: "var(--color-primary)" }}>{chunk.page_number ? `Page ${chunk.page_number}` : chunk.slide_number ? `Slide ${chunk.slide_number}` : documentPreview.title}</p><p className="whitespace-pre-wrap text-sm leading-6">{chunk.text}</p></article>)}</div>}</div>}</section></div>}
    </div>
  );
}
