// src/components/handbook/PhotoUpload.tsx
/**
 * PhotoUpload — компонент завантаження фото персони.
 * Підтримує:
 *  - drag-and-drop або вибір файлу (конвертація в base64 для preview)
 *  - введення URL вручну
 *  - preview з заглушкою-ініціалами
 *  - скидання
 */
import { useState, useRef, useCallback } from "react";
import { Upload, X, Link2, Image, Camera } from "lucide-react";
import { cn } from "../../lib/utils";
import { inputCls } from "./ui";

interface Props {
  value: string; // URL або base64
  onChange: (v: string) => void;
  name?: string; // для ініціалів-заглушки
  className?: string;
}

type Mode = "preview" | "url" | "upload";

export const PhotoUpload = ({
  value,
  onChange,
  name = "",
  className,
}: Props) => {
  const [mode, setMode] = useState<Mode>(value ? "preview" : "upload");
  const [urlInput, setUrlInput] = useState(
    value.startsWith("http") ? value : "",
  );
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const initials = name
    .split(" ")
    .map((p) => p[0] ?? "")
    .slice(0, 2)
    .join("")
    .toUpperCase();

  // ── File handling ─────────────────────────────────────────────────────────

  const processFile = useCallback(
    (file: File) => {
      setUploadError(null);
      if (!file.type.startsWith("image/")) {
        setUploadError("Лише зображення (jpg, png, webp, gif)");
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        setUploadError("Файл занадто великий (макс. 5 МБ)");
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result as string;
        onChange(result);
        setMode("preview");
      };
      reader.readAsDataURL(file);
    },
    [onChange],
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  // ── URL apply ─────────────────────────────────────────────────────────────

  const applyUrl = () => {
    const url = urlInput.trim();
    if (!url) return;
    onChange(url);
    setMode("preview");
  };

  // ── Clear ─────────────────────────────────────────────────────────────────

  const clear = () => {
    onChange("");
    setUrlInput("");
    setMode("upload");
    setUploadError(null);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={cn("space-y-3", className)}>
      {/* Preview zone */}
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="flex-shrink-0 relative group">
          <div className="w-20 h-20 rounded-xl overflow-hidden bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 flex items-center justify-center">
            {value ? (
              <img
                src={value}
                alt={name}
                className="w-full h-full object-cover"
                onError={() => {
                  onChange("");
                  setMode("upload");
                }}
              />
            ) : (
              <span className="text-2xl font-bold text-slate-400 dark:text-slate-500 dark:text-slate-400">
                {initials || (
                  <Image className="w-7 h-7 text-slate-400 dark:text-slate-600" />
                )}
              </span>
            )}
          </div>
          {value && (
            <button
              type="button"
              onClick={clear}
              className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 border border-slate-950 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <X className="w-3 h-3 text-slate-900 dark:text-white" />
            </button>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex-1 space-y-2 pt-1">
          <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400 mb-2">
            {value ? "Фото встановлено" : "Додати фото персони"}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setMode("upload");
                setTimeout(() => fileRef.current?.click(), 50);
              }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                mode === "upload"
                  ? "bg-blue-500/15 border-blue-500/30 text-blue-400"
                  : "bg-white dark:bg-slate-100 dark:bg-slate-800/60 border-slate-300 dark:border-slate-700 text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:text-white hover:border-slate-400 dark:hover:border-slate-600",
              )}
            >
              <Upload className="w-3.5 h-3.5" />
              Завантажити файл
            </button>
            <button
              type="button"
              onClick={() => setMode(mode === "url" ? "upload" : "url")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                mode === "url"
                  ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                  : "bg-white dark:bg-slate-100 dark:bg-slate-800/60 border-slate-300 dark:border-slate-700 text-slate-400 dark:text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:text-white hover:border-slate-400 dark:hover:border-slate-600",
              )}
            >
              <Link2 className="w-3.5 h-3.5" />
              URL
            </button>
          </div>
        </div>
      </div>

      {/* URL input */}
      {mode === "url" && (
        <div className="flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com/photo.jpg"
            className={cn(inputCls, "flex-1")}
            onKeyDown={(e) => {
              if (e.key === "Enter") applyUrl();
            }}
          />
          <button
            type="button"
            onClick={applyUrl}
            disabled={!urlInput.trim()}
            className="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-slate-900 dark:text-white text-sm font-medium disabled:opacity-50 transition-colors"
          >
            OK
          </button>
        </div>
      )}

      {/* Drop zone */}
      {mode === "upload" && !value && (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileRef.current?.click()}
          className={cn(
            "flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all",
            isDragging
              ? "border-blue-500/60 bg-blue-500/5"
              : "border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600 hover:bg-slate-100 dark:bg-slate-100/50 dark:bg-slate-800/30",
          )}
        >
          <Camera className="w-6 h-6 text-slate-400 dark:text-slate-500" />
          <div className="text-center">
            <p className="text-xs text-slate-400 dark:text-slate-500 dark:text-slate-400">
              Перетягніть фото або{" "}
              <span className="text-blue-400 underline">виберіть файл</span>
            </p>
            <p className="text-[11px] text-slate-400 dark:text-slate-600 mt-0.5">
              JPG, PNG, WEBP — до 5 МБ
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {uploadError && (
        <p className="text-xs text-red-400 flex items-center gap-1.5">
          <X className="w-3 h-3" />
          {uploadError}
        </p>
      )}

      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );
};
