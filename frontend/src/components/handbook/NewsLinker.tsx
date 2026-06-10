// src/components/handbook/NewsLinker.tsx
/**
 * NewsLinkerV2 — прив'язка статті (або виділеного фрагменту) до сутності довідника.
 *
 * Оновлено:
 * - Використовує React Portal для відображення поверх будь-яких контейнерів (overflow-hidden)
 * - Динамічне та надійне позиціонування відносно кнопки-тригера
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Link2,
  X,
  Check,
  Loader2,
  Search,
  Building2,
  Users,
  Globe2,
  Plus,
  Quote,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { handbookApi } from "../../api/handbook";
import type { SearchResult, NewsLink } from "../../api/handbook";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  articleId?: string;
  generatedNewsId?: string;
  selectedText?: string;
  compact?: boolean;
  onLinked?: (link: NewsLink) => void;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ENTITY_ICONS: Record<string, typeof Globe2> = {
  country: Globe2,
  org_unit: Building2,
  person: Users,
};

const ENTITY_LABELS: Record<string, string> = {
  country: "Країна",
  org_unit: "Структура",
  person: "Персона",
};

const ENTITY_ORDER = ["country", "org_unit", "person"];

// ── Component ─────────────────────────────────────────────────────────────────

export const NewsLinkerV2 = ({
  articleId,
  generatedNewsId,
  selectedText = "",
  compact = false,
  onLinked,
}: Props) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [note, setNote] = useState("");
  const [excerpt, setExcerpt] = useState(selectedText);
  const [useExcerpt, setUseExcerpt] = useState(!!selectedText);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [pinned, setPinned] = useState(false);
  const [showExisting, setShowExisting] = useState(false);

  // Стан для динамічного трекінгу координат тригера
  const [coords, setCoords] = useState({
    top: 0,
    left: 0,
    width: 0,
    height: 0,
  });

  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  // Оновити excerpt при зміні виділеного тексту ззовні
  useEffect(() => {
    if (selectedText) {
      setExcerpt(selectedText);
      setUseExcerpt(true);
    }
  }, [selectedText]);

  // Функція вирахування абсолютних координат на сторінці
  const updateCoords = useCallback(() => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setCoords({
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        height: rect.height,
      });
    }
  }, []);

  // Оновлення позиції при взаємодії та скролі (включаючи скрол у контейнерах-панелях)
  useEffect(() => {
    if (open) {
      updateCoords();

      const handleScrollResize = () => {
        updateCoords();
      };

      // Слухаємо скрол на етапі capture, щоб ловити прокрутку всередині drawers
      window.addEventListener("scroll", handleScrollResize, true);
      window.addEventListener("resize", handleScrollResize);

      return () => {
        window.removeEventListener("scroll", handleScrollResize, true);
        window.removeEventListener("resize", handleScrollResize);
      };
    }
  }, [open, updateCoords]);

  // Закрити при кліку поза межами поповера та кнопки
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  // Search
  const { data: searchData, isLoading: searching } = useQuery({
    queryKey: ["handbook-search-linker-v2", q],
    queryFn: () => handbookApi.search(q),
    enabled: q.trim().length >= 2 && !selected,
    staleTime: 30_000,
  });

  // Group results by entity_type
  const groupedResults = searchData?.items.reduce(
    (acc, item) => {
      if (!acc[item.entity_type]) acc[item.entity_type] = [];
      acc[item.entity_type].push(item);
      return acc;
    },
    {} as Record<string, SearchResult[]>,
  );

  // Existing links
  const linkKey = articleId
    ? ["handbook-links-article", articleId]
    : ["handbook-links-news", generatedNewsId];

  const { data: existingLinks } = useQuery({
    queryKey: linkKey,
    queryFn: () => {
      if (articleId) return handbookApi.getLinksForArticle(articleId);
      if (generatedNewsId)
        return handbookApi.getLinksForGeneratedNews(generatedNewsId);
      return Promise.resolve([] as NewsLink[]);
    },
    enabled: open && (!!articleId || !!generatedNewsId),
  });

  // Create link
  const { mutate: createLink, isPending } = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("No entity selected");
      const payload: Partial<NewsLink> & { excerpt?: string } = {
        article_id: articleId,
        generated_news_id: generatedNewsId,
        entity_type: selected.entity_type,
        country_id:
          selected.entity_type === "country" ? selected.id : undefined,
        org_unit_id:
          selected.entity_type === "org_unit" ? selected.id : undefined,
        person_id: selected.entity_type === "person" ? selected.id : undefined,
        note: note || undefined,
        excerpt: useExcerpt && excerpt ? excerpt : undefined,
        pinned_by: "user",
      };
      return handbookApi.createNewsLink(payload, "user");
    },
    onSuccess: (link) => {
      setPinned(true);
      qc.invalidateQueries({ queryKey: linkKey });
      onLinked?.(link);
      setTimeout(() => {
        setOpen(false);
        setPinned(false);
        setSelected(null);
        setQ("");
        setNote("");
        setExcerpt(selectedText);
        setUseExcerpt(!!selectedText);
      }, 1200);
    },
  });

  const { mutate: removeLink } = useMutation({
    mutationFn: (linkId: string) => handbookApi.deleteNewsLink(linkId),
    onSuccess: () => qc.invalidateQueries({ queryKey: linkKey }),
  });

  const linksCount = existingLinks?.length ?? 0;
  const hasExcerpt = !!excerpt && excerpt.trim().length > 0;

  // Розрахунок напрямку відкриття (зверху чи знизу) залежно від простору на екрані
  const popoverWidth = 340;
  const buttonViewportTop = coords.top - window.scrollY;
  const spaceBelow = window.innerHeight - (buttonViewportTop + coords.height);
  const showAbove = spaceBelow < 320 && buttonViewportTop > 320;

  const popoverStyle: React.CSSProperties = {
    position: "absolute",
    zIndex: 9999,
    width: `${popoverWidth}px`,
    left: `${Math.max(10, coords.left + coords.width - popoverWidth)}px`,
    top: showAbove
      ? `${coords.top - 8}px`
      : `${coords.top + coords.height + 8}px`,
    transform: showAbove ? "translateY(-100%)" : "none",
  };

  return (
    <div className="inline-block">
      {/* Trigger */}
      <button
        ref={buttonRef}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-1.5 rounded-lg border transition-all duration-150",
          "font-medium text-xs active:scale-95",
          compact ? "px-2 py-1 min-h-[28px]" : "px-3 py-1.5 min-h-[32px]",
          open
            ? "bg-violet-500/15 border-violet-500/30 text-violet-300"
            : "text-slate-400 dark:text-slate-500 border-slate-300 dark:border-slate-700 hover:border-violet-500/40 hover:text-violet-400 hover:bg-violet-500/5",
          hasExcerpt && !open && "border-violet-500/40 text-violet-400",
        )}
        title={
          hasExcerpt
            ? `Прив'язати фрагмент: «${excerpt.slice(0, 40)}…»`
            : "Прив'язати до довідника"
        }
      >
        {hasExcerpt ? (
          <Quote className={cn(compact ? "w-3.5 h-3.5" : "w-4 h-4")} />
        ) : (
          <BookOpen className={cn(compact ? "w-3.5 h-3.5" : "w-4 h-4")} />
        )}
        {!compact && <span>Довідник</span>}
        {linksCount > 0 && (
          <span className="rounded-full px-1.5 py-0.5 text-[10px] font-mono bg-violet-500/20 text-violet-400">
            {linksCount}
          </span>
        )}
        {hasExcerpt && (
          <span className="rounded-full px-1.5 py-0.5 text-[10px] font-mono bg-amber-500/20 text-amber-400">
            фрагмент
          </span>
        )}
      </button>

      {/* Popover за допомогою React Portal */}
      {open &&
        createPortal(
          <div
            ref={panelRef}
            style={popoverStyle}
            className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[420px]"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
              <p className="text-xs font-medium text-slate-900 dark:text-white flex items-center gap-2">
                <Link2 className="w-3.5 h-3.5 text-violet-400" />
                Прив'язати до довідника
              </p>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-400 dark:text-slate-600 hover:text-slate-900 dark:text-white transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto min-h-0">
              {/* Excerpt preview */}
              {hasExcerpt && (
                <div className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
                  <div className="flex items-start gap-2">
                    <button
                      onClick={() => setUseExcerpt((v) => !v)}
                      className={cn(
                        "flex-shrink-0 mt-0.5 w-4 h-4 rounded border transition-colors",
                        useExcerpt
                          ? "bg-violet-600 border-violet-600"
                          : "bg-transparent border-slate-600",
                      )}
                    >
                      {useExcerpt && (
                        <Check className="w-3 h-3 text-slate-900 dark:text-white m-auto" />
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase mb-1">
                        {useExcerpt
                          ? "Фрагмент буде збережено"
                          : "Зберегти фрагмент"}
                      </p>
                      <blockquote
                        className={cn(
                          "text-[11px] leading-relaxed pl-2 border-l-2 italic line-clamp-3 transition-colors",
                          useExcerpt
                            ? "text-slate-700 dark:text-slate-300 border-violet-500/50"
                            : "text-slate-400 dark:text-slate-600 border-slate-300 dark:border-slate-700 line-through",
                        )}
                      >
                        {excerpt.slice(0, 200)}
                        {excerpt.length > 200 ? "…" : ""}
                      </blockquote>
                    </div>
                  </div>
                </div>
              )}

              {/* Existing links (collapsible) */}
              {existingLinks && existingLinks.length > 0 && (
                <div className="border-b border-slate-200 dark:border-slate-200/60 dark:border-slate-800/60">
                  <button
                    onClick={() => setShowExisting((v) => !v)}
                    className="w-full flex items-center justify-between px-3 py-2 text-[10px] text-slate-400 dark:text-slate-500 hover:text-slate-400 dark:text-slate-500 transition-colors"
                  >
                    <span className="font-mono uppercase">
                      Вже прив'язано ({existingLinks.length})
                    </span>
                    {showExisting ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                  {showExisting && (
                    <div className="px-3 pb-2 space-y-1.5">
                      {existingLinks.map((link) => {
                        const Icon = ENTITY_ICONS[link.entity_type] ?? BookOpen;
                        return (
                          <div
                            key={link.id}
                            className="flex items-center gap-2 group"
                          >
                            <Icon className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <span className="text-xs text-slate-400 dark:text-slate-500 truncate block">
                                {ENTITY_LABELS[link.entity_type]}
                                {link.note && ` · ${link.note}`}
                              </span>
                              {(link as any).excerpt && (
                                <span className="text-[10px] text-slate-400 dark:text-slate-600 italic truncate block">
                                  «{(link as any).excerpt.slice(0, 50)}…»
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => removeLink(link.id)}
                              className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 dark:text-slate-600 hover:text-red-400 transition-all"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Search or confirm */}
              {!selected ? (
                <div className="p-3 space-y-2">
                  {/* Search input */}
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                    <Search className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 flex-shrink-0" />
                    <input
                      ref={inputRef}
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      placeholder="Знайти країну, структуру, персону…"
                      className="flex-1 bg-transparent text-xs text-slate-900 dark:text-white placeholder-slate-600 outline-none"
                    />
                    {searching && (
                      <Loader2 className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 animate-spin flex-shrink-0" />
                    )}
                  </div>

                  {/* Results grouped */}
                  {groupedResults && (
                    <div className="max-h-52 overflow-y-auto space-y-2">
                      {ENTITY_ORDER.filter(
                        (t) => groupedResults[t]?.length,
                      ).map((entityType) => (
                        <div key={entityType}>
                          <p className="px-1 mb-0.5 text-[9px] font-mono text-slate-400 dark:text-slate-600 uppercase tracking-widest">
                            {ENTITY_LABELS[entityType]}
                          </p>
                          {groupedResults[entityType].map((item) => {
                            const Icon =
                              ENTITY_ICONS[item.entity_type] ?? BookOpen;
                            return (
                              <button
                                key={item.id}
                                onClick={() => setSelected(item)}
                                className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-white dark:bg-slate-100 dark:bg-slate-800/60 transition-colors text-left"
                              >
                                <div className="w-6 h-6 rounded-md bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                                  <Icon className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs text-slate-900 dark:text-white truncate">
                                    {item.title}
                                  </p>
                                  {item.country_name && (
                                    <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate">
                                      {item.country_name}
                                    </p>
                                  )}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  )}

                  {q.length >= 2 && !searching && !searchData?.items.length && (
                    <p className="text-center text-xs text-slate-400 dark:text-slate-600 py-3">
                      Нічого не знайдено
                    </p>
                  )}
                </div>
              ) : (
                /* Confirm */
                <div className="p-3 space-y-3">
                  {/* Selected entity */}
                  <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/10 border border-violet-500/20 rounded-lg">
                    {(() => {
                      const Icon =
                        ENTITY_ICONS[selected.entity_type] ?? BookOpen;
                      return (
                        <Icon className="w-4 h-4 text-violet-400 flex-shrink-0" />
                      );
                    })()}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-900 dark:text-white truncate">
                        {selected.title}
                      </p>
                      <p className="text-[10px] text-slate-400 dark:text-slate-500">
                        {ENTITY_LABELS[selected.entity_type]}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setSelected(null);
                        setNote("");
                      }}
                      className="text-slate-400 dark:text-slate-600 hover:text-slate-900 dark:text-white transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Note */}
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Примітка до зв'язку (необов'язково)…"
                    rows={2}
                    className={cn(
                      "w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2",
                      "text-xs text-slate-900 dark:text-white placeholder-slate-600 outline-none resize-none",
                      "focus:border-violet-500/40 transition-colors",
                    )}
                  />

                  {/* Confirm button */}
                  <button
                    onClick={() => createLink()}
                    disabled={isPending || pinned}
                    className={cn(
                      "w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-all",
                      pinned
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-violet-600 hover:bg-violet-500 text-slate-900 dark:text-white",
                      "disabled:opacity-60",
                    )}
                  >
                    {isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : pinned ? (
                      <>
                        <Check className="w-3.5 h-3.5" /> Прив'язано!
                      </>
                    ) : (
                      <>
                        <Plus className="w-3.5 h-3.5" /> Прив'язати
                        {useExcerpt && hasExcerpt ? " фрагмент" : ""}
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
};

// ── Hook: capture text selection ──────────────────────────────────────────────

export const useTextSelection = (
  containerRef?: React.RefObject<HTMLElement>,
) => {
  const [selectedText, setSelectedText] = useState("");

  useEffect(() => {
    const handler = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        return;
      }
      const text = sel.toString().trim();
      if (!text) return;

      if (containerRef?.current) {
        const range = sel.getRangeAt(0);
        if (!containerRef.current.contains(range.commonAncestorContainer))
          return;
      }

      if (text.length >= 10) {
        setSelectedText(text);
      }
    };

    document.addEventListener("mouseup", handler);
    document.addEventListener("touchend", handler);
    return () => {
      document.removeEventListener("mouseup", handler);
      document.removeEventListener("touchend", handler);
    };
  }, [containerRef]);

  const clearSelection = useCallback(() => setSelectedText(""), []);

  return { selectedText, clearSelection };
};
