// src/components/articles/ArticleDrawer.tsx
import { useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, ExternalLink, Calendar, Globe, ChevronLeft } from "lucide-react";
import { useArticle } from "../../hooks/useArticles";
import { ScoreBadge } from "./ScoreBadge";
import { ArticleBadge } from "./ArticleBadge";
import { TagsList } from "./TagsList";
import { FeedbackButtons } from "./FeedbackButtons";
import { NewsLinkerV2, useTextSelection } from "../handbook/NewsLinker";
import { cn, formatDateFull } from "../../lib/utils";
import { getLangMeta, flagImgProps } from "../../lib/languages";

interface Props {
  articleId: string | null;
  onClose: () => void;
}

const FlagImg = ({ lang, className }: { lang: string; className?: string }) => {
  const meta = getLangMeta(lang);
  if (!meta.country) return null;
  return (
    <img
      {...flagImgProps(meta.country)}
      alt={meta.label}
      className={cn("inline-block rounded-sm object-cover", className)}
    />
  );
};

export const ArticleDrawer = ({ articleId, onClose }: Props) => {
  const { data: article, isLoading } = useArticle(articleId);
  const bodyRef = useRef<HTMLDivElement>(null);
  const { selectedText, clearSelection } = useTextSelection(bodyRef as any);

  return (
    <AnimatePresence>
      {articleId && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 dark:bg-black/50 z-40 backdrop-blur-sm hidden md:block"
            onClick={onClose}
          />

          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className={cn(
              "fixed inset-0 z-50",
              "md:left-auto md:right-0 md:top-0 md:bottom-0 md:inset-y-0 md:w-full md:max-w-2xl",
              "bg-white dark:bg-slate-900",
              "border-l border-slate-200 dark:border-slate-800",
              "flex flex-col shadow-2xl",
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
              <div className="flex items-center gap-2">
                <button
                  onClick={onClose}
                  className="md:hidden mr-1 p-1.5 -ml-1 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                {article && <ArticleBadge status={article.status} />}
                {article && <ScoreBadge score={article.relevance_score} />}
              </div>
              <div className="hidden md:flex items-center gap-2">
                {article && (
                  <NewsLinkerV2
                    articleId={article.id}
                    selectedText={selectedText}
                    compact
                  />
                )}
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto overscroll-contain">
              {isLoading && (
                <div className="flex items-center justify-center h-48">
                  <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}

              {article && (
                <div className="p-4 sm:p-6 space-y-4">
                  <AnimatePresence>
                    {selectedText && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20"
                      >
                        <span className="text-xs text-violet-400 flex-1 truncate">
                          ✂️ «{selectedText.slice(0, 70)}
                          {selectedText.length > 70 ? "…" : ""}»
                        </span>
                        <NewsLinkerV2
                          articleId={article.id}
                          selectedText={selectedText}
                          compact
                        />
                        <button
                          onClick={clearSelection}
                          className="text-violet-600 hover:text-violet-400 text-[10px] font-mono whitespace-nowrap transition-colors"
                        >
                          скинути
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white leading-tight">
                    {article.title}
                  </h1>

                  <div className="flex flex-wrap gap-3 text-sm text-slate-400 dark:text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 flex-shrink-0" />
                      <FlagImg
                        lang={article.language}
                        className="w-[18px] h-[13px] flex-shrink-0"
                      />
                      {getLangMeta(article.language).label} (
                      {article.language.toUpperCase()})
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 flex-shrink-0" />
                      {formatDateFull(article.published_at)}
                    </span>
                  </div>

                  <TagsList tags={article.tags} clickable />

                  <div
                    ref={bodyRef}
                    className="prose prose-sm dark:prose-invert max-w-none prose-slate select-text"
                  >
                    <p className="text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap text-sm sm:text-base">
                      {article.body}
                    </p>
                  </div>

                  <p className="text-[11px] text-slate-400 dark:text-slate-500 italic">
                    💡 Виділіть текст, щоб прив'язати фрагмент до довідника
                  </p>
                </div>
              )}
            </div>

            {/* Footer */}
            {article && (
              <div
                className={cn(
                  "px-4 sm:px-6 py-3 sm:py-4 border-t border-slate-200 dark:border-slate-800 flex-shrink-0",
                  "flex items-center justify-between gap-4 pb-safe",
                )}
              >
                <FeedbackButtons
                  articleId={article.id}
                  initialLiked={article.user_liked ?? null}
                />
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    "flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-sm font-medium",
                    "bg-blue-500 hover:bg-blue-600 active:bg-blue-700 text-white transition-colors",
                    "flex-shrink-0",
                  )}
                >
                  <ExternalLink className="w-4 h-4" />
                  <span className="hidden xs:inline">Відкрити оригінал</span>
                  <span className="xs:hidden">Відкрити</span>
                </a>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
};
