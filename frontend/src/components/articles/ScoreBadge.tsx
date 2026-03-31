// src/components/articles/ScoreBadge.tsx
// Design: Editorial Dark — golden accent system
import { cn } from "../../lib/utils";

interface Props {
  score: number;
  className?: string;
}

const getScoreStyle = (score: number) => {
  if (score >= 0.8)
    return "bg-amber-500/15 text-amber-400 border-amber-500/30 shadow-amber-500/10";
  if (score >= 0.6)
    return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 shadow-emerald-500/10";
  if (score >= 0.4)
    return "bg-sky-500/15 text-sky-400 border-sky-500/30 shadow-sky-500/10";
  return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
};

const getScoreBar = (score: number) => {
  const pct = Math.round(score * 100);
  if (pct >= 80) return "█████";
  if (pct >= 60) return "████░";
  if (pct >= 40) return "███░░";
  if (pct >= 20) return "██░░░";
  return "█░░░░";
};

export const ScoreBadge = ({ score, className }: Props) => (
  <span
    className={cn(
      "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-semibold border shadow-sm",
      getScoreStyle(score),
      className,
    )}
  >
    <span className="tracking-[-0.05em] text-[10px] opacity-60">
      {getScoreBar(score)}
    </span>
    <span>{score.toFixed(2)}</span>
  </span>
);
