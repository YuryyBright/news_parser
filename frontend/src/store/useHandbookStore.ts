// src/store/useHandbookStore.ts
import { create } from "zustand";
import type {
  Country,
  CountryDetail,
  OrgUnit,
  Person,
  SearchResult,
} from "../api/handbook";

export type HandbookView = "tree" | "table" | "orgchart" | "list" | "chart";
export type HandbookTab = "org" | "persons" | "news" | "changelog";

interface HandbookStore {
  // Country list
  countries: Country[];
  totalCountries: number;
  countriesPage: number;
  countriesSearch: string;

  // Active country detail
  activeCountryId: string | null;
  activeCountry: CountryDetail | null;

  // Active entity within country
  activeOrgUnitId: string | null;
  activePersonId: string | null;

  // View mode
  view: HandbookView;
  activeTab: HandbookTab;

  // Expanded nodes in tree
  expandedNodes: Set<string>;

  // Search
  searchQuery: string;
  searchResults: SearchResult[];
  isSearchOpen: boolean;

  // UI
  isFormOpen: boolean;
  formEntity: "country" | "org_unit" | "person" | null;
  formData: Record<string, unknown> | null;

  // Actions
  setCountries: (countries: Country[], total: number) => void;
  setCountriesPage: (page: number) => void;
  setCountriesSearch: (q: string) => void;

  setActiveCountry: (id: string | null, detail?: CountryDetail) => void;
  setActiveCountryDetail: (detail: CountryDetail) => void;

  setActiveOrgUnit: (id: string | null) => void;
  setActivePerson: (id: string | null) => void;

  setView: (view: HandbookView) => void;
  setActiveTab: (tab: HandbookTab) => void;

  toggleNode: (nodeId: string) => void;
  expandNode: (nodeId: string) => void;
  collapseAll: () => void;
  expandAll: (ids: string[]) => void;

  setSearchQuery: (q: string) => void;
  setSearchResults: (results: SearchResult[]) => void;
  openSearch: () => void;
  closeSearch: () => void;

  openForm: (
    entity: "country" | "org_unit" | "person",
    data?: Record<string, unknown>,
  ) => void;
  closeForm: () => void;
}

export const useHandbookStore = create<HandbookStore>((set, get) => ({
  countries: [],
  totalCountries: 0,
  countriesPage: 1,
  countriesSearch: "",

  activeCountryId: null,
  activeCountry: null,
  activeOrgUnitId: null,
  activePersonId: null,

  view: "tree",
  activeTab: "org",

  expandedNodes: new Set<string>(),

  searchQuery: "",
  searchResults: [],
  isSearchOpen: false,

  isFormOpen: false,
  formEntity: null,
  formData: null,

  setCountries: (countries, total) => set({ countries, totalCountries: total }),
  setCountriesPage: (page) => set({ countriesPage: page }),
  setCountriesSearch: (q) => set({ countriesSearch: q, countriesPage: 1 }),

  setActiveCountry: (id, detail) =>
    set({
      activeCountryId: id,
      activeCountry: detail ?? null,
      activeOrgUnitId: null,
      activePersonId: null,
      expandedNodes: new Set(),
    }),

  setActiveCountryDetail: (detail) => set({ activeCountry: detail }),

  setActiveOrgUnit: (id) => set({ activeOrgUnitId: id, activePersonId: null }),
  setActivePerson: (id) => set({ activePersonId: id }),

  setView: (view) => set({ view }),
  setActiveTab: (tab) => set({ activeTab: tab }),

  toggleNode: (nodeId) =>
    set((s) => {
      const next = new Set(s.expandedNodes);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return { expandedNodes: next };
    }),

  expandNode: (nodeId) =>
    set((s) => ({ expandedNodes: new Set([...s.expandedNodes, nodeId]) })),

  collapseAll: () => set({ expandedNodes: new Set() }),

  expandAll: (ids) => set({ expandedNodes: new Set(ids) }),

  setSearchQuery: (q) => set({ searchQuery: q }),
  setSearchResults: (results) => set({ searchResults: results }),
  openSearch: () => set({ isSearchOpen: true }),
  closeSearch: () =>
    set({ isSearchOpen: false, searchQuery: "", searchResults: [] }),

  openForm: (entity, data) =>
    set({ isFormOpen: true, formEntity: entity, formData: data ?? null }),
  closeForm: () => set({ isFormOpen: false, formEntity: null, formData: null }),
}));
