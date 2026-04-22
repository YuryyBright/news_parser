// src/lib/languages.ts
// Single source of truth for language metadata.
// Uses inline SVG flag icons instead of emoji flags
// because Chrome on Windows does not render flag emoji.

export interface LangMeta {
  label: string;
  /** Two-letter ISO 3166-1 country code for the flag (lowercase) */
  country: string;
}

const LANGUAGE_META: Record<string, LangMeta> = {
  uk: { label: "Укр", country: "ua" },
  en: { label: "Eng", country: "gb" },
  de: { label: "Deu", country: "de" },
  fr: { label: "Fra", country: "fr" },
  pl: { label: "Pol", country: "pl" },
  ru: { label: "Рус", country: "ru" },
  hu: { label: "Hun", country: "hu" },
  ro: { label: "Rou", country: "ro" },
  sk: { label: "Slo", country: "sk" },
};

export const getLangMeta = (lang: string): LangMeta =>
  LANGUAGE_META[lang?.toLowerCase()] ?? {
    label: lang?.toUpperCase() ?? "??",
    country: "",
  };

/**
 * Returns a URL to a country flag SVG via flagcdn.com (free, no auth needed).
 * Falls back to an empty string if no country code is available.
 *
 * Usage:  <img src={getFlagUrl("ua")} alt="UA" className="w-4 h-3 object-cover rounded-sm" />
 */
export const getFlagUrl = (country: string): string =>
  country ? `https://flagcdn.com/w20/${country}.png` : "";

/**
 * Ready-made <img> props for a flag.
 * Drop these directly onto an <img> element.
 */
export const flagImgProps = (country: string) => ({
  src: getFlagUrl(country),
  // 2× for retina
  srcSet: country ? `https://flagcdn.com/w40/${country}.png 2x` : undefined,
  width: 20,
  height: 15,
  loading: "lazy" as const,
  decoding: "async" as const,
  style: { borderRadius: "2px", objectFit: "cover" as const, flexShrink: 0 },
});
