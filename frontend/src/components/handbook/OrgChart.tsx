// src/components/handbook/OrgChart.tsx
/**
 * OrgChart — інтерактивна деревовидна діаграма організаційної структури.
 * Рендерить SVG-дерево з картками підрозділів і персон.
 * Підтримує zoom/pan, collapse/expand вузлів.
 */
import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "../../lib/utils";
import type { OrgUnit, Person } from "../../api/handbook";
import { fullName } from "../../api/handbook";
import { ZoomIn, ZoomOut, Maximize2, RefreshCw, Download } from "lucide-react";
// Додайте ці імпорти на початку файлу
import { toPng } from "html-to-image";
import jsPDF from "jspdf";
// ── Layout constants ──────────────────────────────────────────────────────────

// ── Layout constants ──────────────────────────────────────────────────────────
const NODE_W = 280; // Трохи ширша картка для тексту
const NODE_H = 148; // Більше висоти для посади
const H_GAP = 50;
const V_GAP = 70;

// ── Color map for unit types ──────────────────────────────────────────────────

const TYPE_COLORS: Record<
  string,
  { bg: string; border: string; text: string }
> = {
  ministry: { bg: "#7c3aed1a", border: "#7c3aed60", text: "#a78bfa" },
  department: { bg: "#1d4ed81a", border: "#1d4ed860", text: "#60a5fa" },
  division: { bg: "#0369a11a", border: "#0369a160", text: "#38bdf8" },
  sector: { bg: "а#0f766e1a", border: "#0f766e60", text: "#2dd4bf" },
  agency: { bg: "#b4530a1a", border: "#b4530a60", text: "#fbbf24" },
  service: { bg: "#c2410c1a", border: "#c2410c60", text: "#fb923c" },
  command: { bg: "#9f12321a", border: "#9f123260", text: "#f87171" },
  default: { bg: "#1e293b", border: "#334155", text: "#94a3b8" },
};

// ── Tree layout algorithm ─────────────────────────────────────────────────────

interface LayoutNode {
  unit: OrgUnit;
  x: number;
  y: number;
  width: number;
  children: LayoutNode[];
  collapsed: boolean;
}

function subtreeWidth(unit: OrgUnit, collapsed: Set<string>): number {
  if (collapsed.has(unit.id) || unit.children.length === 0) {
    return NODE_W;
  }
  const childWidths = unit.children.map((c) => subtreeWidth(c, collapsed));
  const total = childWidths.reduce((sum, w) => sum + w, 0);
  return Math.max(NODE_W, total + H_GAP * (unit.children.length - 1));
}

function layoutTree(
  unit: OrgUnit,
  x: number,
  y: number,
  collapsed: Set<string>,
): LayoutNode {
  const width = subtreeWidth(unit, collapsed);
  const childNodes: LayoutNode[] = [];

  if (!collapsed.has(unit.id) && unit.children.length > 0) {
    const totalChildWidth =
      unit.children.reduce((sum, c) => sum + subtreeWidth(c, collapsed), 0) +
      H_GAP * (unit.children.length - 1);
    let cx = x - totalChildWidth / 2;
    for (const child of unit.children) {
      const cw = subtreeWidth(child, collapsed);
      childNodes.push(
        layoutTree(child, cx + cw / 2, y + NODE_H + V_GAP, collapsed),
      );
      cx += cw + H_GAP;
    }
  }

  return {
    unit,
    x,
    y: y,
    width,
    children: childNodes,
    collapsed: collapsed.has(unit.id),
  };
}

function collectNodes(
  node: LayoutNode,
  result: LayoutNode[] = [],
): LayoutNode[] {
  result.push(node);
  node.children.forEach((c) => collectNodes(c, result));
  return result;
}

function collectEdges(
  node: LayoutNode,
  result: { x1: number; y1: number; x2: number; y2: number }[] = [],
) {
  node.children.forEach((child) => {
    result.push({
      x1: node.x,
      y1: node.y + NODE_H,
      x2: child.x,
      y2: child.y,
    });
    collectEdges(child, result);
  });
  return result;
}

// ── OrgNode SVG element ───────────────────────────────────────────────────────

const OrgNode = ({
  node,
  onToggle,
  onSelect,
  onPersonSelect,
  isSelected,
}: {
  node: LayoutNode;
  onToggle: (id: string) => void;
  onSelect: (unit: OrgUnit) => void;
  onPersonSelect?: (person: Person) => void;
  isSelected: boolean;
}) => {
  const { unit, x, y } = node;
  const colors = TYPE_COLORS[unit.unit_type] ?? TYPE_COLORS.default;
  const hasChildren = unit.children.length > 0 || (unit as any)._hasChildren;
  const name = unit.short_name || unit.name;
  const personCount = unit.persons?.length ?? 0;

  const leader = unit.leader;

  return (
    <g
      transform={`translate(${x - NODE_W / 2}, ${y})`}
      style={{ cursor: "pointer" }}
      onClick={() => onSelect(unit)}
    >
      {/* Фон картки */}
      <rect
        width={NODE_W}
        height={NODE_H}
        rx={12}
        fill={colors.bg}
        stroke={isSelected ? "#3b82f6" : colors.border}
        strokeWidth={isSelected ? 2 : 1}
        style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.3))" }}
      />
      {/* Верхня кольорова лінія */}
      <rect
        width={NODE_W}
        height={4}
        rx={12}
        fill={colors.text}
        opacity={0.8}
      />

      {/* Весь контент картки через HTML */}
      <foreignObject x={0} y={4} width={NODE_W} height={NODE_H - 4}>
        <div
          style={{
            padding: "12px",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            boxSizing: "border-box",
          }}
        >
          {/* Назва підрозділу */}
          <div
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#f1f5f9",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              textAlign: "center",
              marginBottom: "8px",
              lineHeight: "1.3",
              maxHeight: "2.6em",
            }}
          >
            {name}
          </div>

          {/* БЛОК КЕРІВНИКА (Велике фото) */}
          {leader ? (
            <div
              onClick={(e) => {
                if (onPersonSelect) {
                  e.stopPropagation();
                  onPersonSelect(leader);
                }
              }}
              style={{
                display: "flex",
                gap: "10px",
                alignItems: "center",
                flex: 1,
                cursor: onPersonSelect ? "pointer" : "default",
                borderRadius: "8px",
                padding: "4px",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                if (onPersonSelect)
                  (e.currentTarget as HTMLDivElement).style.background =
                    "rgba(255,255,255,0.05)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.background =
                  "transparent";
              }}
            >
              {/* Аватар */}
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  flexShrink: 0,
                  backgroundColor: "#1e293b",
                  border: `2px solid ${colors.text}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                }}
              >
                {leader.photo_url ? (
                  <img
                    src={leader.photo_url}
                    alt={fullName(leader)}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                    }}
                  />
                ) : (
                  <span
                    style={{
                      fontSize: "16px",
                      fontWeight: 600,
                      color: "#94a3b8",
                    }}
                  >
                    {leader.first_name?.[0]}
                    {leader.last_name?.[0]}
                  </span>
                )}
              </div>

              {/* Текст */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#ffffff",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    lineHeight: "1.3",
                  }}
                >
                  {fullName(leader)}
                </div>
                <div
                  style={{
                    fontSize: "10px",
                    color: "#94a3b8",
                    marginTop: "2px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    lineHeight: "1.3",
                  }}
                >
                  {/* Відображаємо реальну посаду персони, або дефолтний тайтл керівника з підрозділу */}
                  {leader.position_title || unit.leader_title || "Керівник"}
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#64748b",
                fontSize: "11px",
                fontStyle: "italic",
              }}
            >
              Вакантно
            </div>
          )}

          {/* Тип підрозділу та кількість людей */}
          <div
            style={{
              marginTop: "auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "10px",
              color: colors.text,
              fontFamily: "monospace",
              textTransform: "uppercase",
            }}
          >
            <span>{unit.unit_type}</span>
            {personCount > 0 && <span>{personCount} 👤</span>}
          </div>
        </div>
      </foreignObject>

      {/* Кнопка згортання/розгортання */}
      {hasChildren && (
        <g
          transform={`translate(${NODE_W / 2}, ${NODE_H})`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(unit.id);
          }}
        >
          <circle
            r={12}
            cx={0}
            cy={0}
            fill="#0f172a"
            stroke={colors.border}
            strokeWidth={1.5}
          />
          <text
            x={0}
            y={4}
            textAnchor="middle"
            fontSize={14}
            fontWeight="bold"
            fill={colors.text}
            style={{ userSelect: "none" }}
          >
            {node.collapsed ? "+" : "−"}
          </text>
        </g>
      )}
    </g>
  );
};
// ── Edge ──────────────────────────────────────────────────────────────────────

const Edge = ({
  x1,
  y1,
  x2,
  y2,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}) => {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const path = `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
  return <path d={path} fill="none" stroke="#334155" strokeWidth={1.5} />;
};

// ── Main OrgChart ─────────────────────────────────────────────────────────────

interface Props {
  units: OrgUnit[];
  selectedId?: string | null;
  onSelect?: (unit: OrgUnit) => void;
  onPersonSelect?: (person: Person) => void;
  className?: string;
}

export const OrgChart = ({
  units,
  selectedId,
  onSelect,
  onPersonSelect,
  className,
}: Props) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Build layout for all root units
  const roots = units.filter((u) => !u.parent_id);

  let totalWidth = 0;
  const rootLayouts: LayoutNode[] = [];
  roots.forEach((root) => {
    const w = subtreeWidth(root, collapsed);
    const layout = layoutTree(root, totalWidth + w / 2 + H_GAP, 20, collapsed);
    rootLayouts.push(layout);
    totalWidth += w + H_GAP;
  });

  const allNodes = rootLayouts.flatMap((r) => collectNodes(r));
  const allEdges = rootLayouts.flatMap((r) => collectEdges(r));

  const maxX = allNodes.reduce((m, n) => Math.max(m, n.x + NODE_W / 2), 0);
  const maxY = allNodes.reduce((m, n) => Math.max(m, n.y + NODE_H), 0);
  const svgW = Math.max(maxX + H_GAP, 400);
  const svgH = Math.max(maxY + V_GAP, 200);

  const exportToPDF = async () => {
    if (!containerRef.current) return;

    try {
      // Тимчасово скидаємо зум і зсув, щоб відмалювати все дерево
      const svgNode = containerRef.current.querySelector("svg");
      const originalTransform = svgNode?.style.transform;

      if (svgNode) {
        svgNode.style.transform = "none";
      }

      // Використовуємо html-to-image замість html2canvas
      const dataUrl = await toPng(containerRef.current, {
        backgroundColor: "#020617", // Колір фону (slate-950)
        pixelRatio: 2, // Вища якість (аналог scale: 2)
      });

      // Повертаємо зум назад
      if (svgNode && originalTransform) {
        svgNode.style.transform = originalTransform;
      }

      // Створюємо PDF на основі отриманого зображення
      const img = new Image();
      img.src = dataUrl;
      img.onload = () => {
        const pdf = new jsPDF({
          orientation: img.width > img.height ? "landscape" : "portrait",
          unit: "px",
          format: [img.width, img.height],
        });

        pdf.addImage(dataUrl, "PNG", 0, 0, img.width, img.height);
        pdf.save("org-structure.pdf");
      };
    } catch (error) {
      console.error("Помилка експорту PDF:", error);
      alert("Не вдалося створити PDF.");
    }
  };
  // Pan handlers
  const onMouseDown = (e: React.MouseEvent) => {
    if ((e.target as SVGElement).tagName === "circle") return; // don't pan on toggle
    isPanning.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  };
  const onMouseUp = () => {
    isPanning.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.min(2, Math.max(0.3, z * delta)));
  };

  const toggleCollapse = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const fitView = () => {
    if (!containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    const scaleX = width / svgW;
    const scaleY = height / svgH;
    const scale = Math.min(scaleX, scaleY, 1) * 0.9;
    setZoom(scale);
    setPan({ x: (width - svgW * scale) / 2, y: 20 });
  };

  if (units.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center h-64 text-slate-400 dark:text-slate-500 text-sm",
          className,
        )}
      >
        Немає підрозділів для відображення
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800",
        className,
      )}
    >
      {/* Controls */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1">
        {[
          { icon: Download, action: exportToPDF, title: "Експорт в PDF" },
          {
            icon: ZoomIn,
            action: () => setZoom((z) => Math.min(2, z * 1.2)),
            title: "Збільшити",
          },
          {
            icon: ZoomOut,
            action: () => setZoom((z) => Math.max(0.3, z / 1.2)),
            title: "Зменшити",
          },
          { icon: Maximize2, action: fitView, title: "Вписати" },
          { icon: RefreshCw, action: resetView, title: "Скинути" },
        ].map(({ icon: Icon, action, title }) => (
          <button
            key={title}
            onClick={action}
            title={title}
            className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800/90 border border-slate-300 dark:border-slate-700 flex items-center justify-center text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:text-white hover:border-slate-400 dark:hover:border-slate-600 transition-colors"
          >
            <Icon className="w-3.5 h-3.5" />
          </button>
        ))}
        <div className="px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800/90 border border-slate-300 dark:border-slate-700 text-[10px] font-mono text-slate-400 dark:text-slate-500 dark:text-slate-400">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* SVG canvas */}
      <div
        ref={containerRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onWheel={handleWheel}
        style={{ minHeight: 400 }}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${svgW} ${svgH}`}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "top left",
            transition: isPanning.current ? "none" : "transform 0.1s ease",
          }}
        >
          {/* Grid background */}
          <defs>
            <pattern
              id="grid"
              width="40"
              height="40"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="#1e293b"
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width={svgW} height={svgH} fill="url(#grid)" />

          {/* Edges */}
          <g>
            {allEdges.map((edge, i) => (
              <Edge key={i} {...edge} />
            ))}
          </g>

          {/* Nodes */}
          <g>
            {allNodes.map((node) => (
              <OrgNode
                key={node.unit.id}
                node={node}
                onToggle={toggleCollapse}
                onSelect={(unit) => onSelect?.(unit)}
                onPersonSelect={onPersonSelect}
                isSelected={selectedId === node.unit.id}
              />
            ))}
          </g>
        </svg>
      </div>
    </div>
  );
};
