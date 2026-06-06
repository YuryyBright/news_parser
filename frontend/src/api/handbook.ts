// src/api/handbook.ts
import { client } from "./client";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ResourceLink {
  url: string;
  title: string;
  resource_type: "link" | "document" | "regulation" | "video";
}

export interface ChangeLogEntry {
  id: string;
  entity_type: string;
  changed_by: string;
  action: "created" | "updated" | "deleted";
  field_name?: string;
  old_value?: string;
  new_value?: string;
  diff?: Record<string, { old: unknown; new: unknown }>;
  created_at: string;
}

export interface NewsLink {
  id: string;
  excerpt?: string;
  article_id?: string;
  generated_news_id?: string;
  entity_type: string;
  country_id?: string;
  org_unit_id?: string;
  person_id?: string;
  note?: string;
  pinned_by?: string;
  created_at: string;
}
export interface HandbookEvent {
  id: string;
  person_id?: string | null;
  org_unit_id?: string | null;
  country_id?: string | null;
  title: string;
  event_type: string;
  date: string; // ISO datetime
  location?: string | null;
  description?: string | null;
  participants: string[];
  source_url?: string | null;
  article_id?: string | null;
  generated_news_id?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventCreatePayload {
  person_id?: string;
  org_unit_id?: string;
  country_id?: string;
  title: string;
  event_type: string;
  date: string; // ISO datetime
  location?: string;
  description?: string;
  participants?: string[];
  source_url?: string;
  article_id?: string;
  generated_news_id?: string;
}

export interface Person {
  id: string;
  org_unit_id?: string;
  country_id: string;
  first_name: string;

  last_name: string;
  patronymic?: string;
  position_title?: string;
  rank?: string;
  photo_url?: string;
  bio?: string;
  contacts: Record<string, string>;
  resources: ResourceLink[];
  date_appointed?: string;
  date_dismissed?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  news_links: NewsLink[];
  changelog: ChangeLogEntry[];
}

export interface OrgUnit {
  id: string;
  country_id: string;
  parent_id?: string;
  leader_title?: string;
  leader: Person | null;
  name: string;
  short_name?: string;
  unit_type: string;
  level: number;
  sort_order: number;
  description?: string;
  legal_basis?: string;
  resources: ResourceLink[];
  is_active: boolean;
  valid_from?: string;
  valid_to?: string;
  created_at: string;
  updated_at: string;
  children: OrgUnit[];
  persons: Person[];
  news_links: NewsLink[];
  changelog: ChangeLogEntry[];
}

export interface Country {
  id: string;
  code: string;
  name_uk: string;
  name_en: string;
  flag_emoji?: string;
  capital?: string;
  description?: string;
  resources: ResourceLink[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  org_units_count: number;
  persons_count: number;
}

export interface CountryDetail extends Country {
  org_units: OrgUnit[];
  changelog: ChangeLogEntry[];
  news_links: NewsLink[];
}

export interface SearchResult {
  entity_type: "country" | "org_unit" | "person";
  id: string;
  title: string;
  subtitle?: string;
  country_code?: string;
  country_name?: string;
}

export interface PaginatedCountries {
  items: Country[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ── Helper ─────────────────────────────────────────────────────────────────────
export function buildTree(flatUnits: OrgUnit[]): OrgUnit[] {
  const map = new Map<string, OrgUnit>();
  const roots: OrgUnit[] = [];

  // Clone to avoid mutating
  const units = flatUnits.map((u) => ({ ...u, children: [] }));
  units.forEach((u) => map.set(u.id, u));
  units.forEach((u) => {
    if (u.parent_id && map.has(u.parent_id)) {
      map.get(u.parent_id)!.children.push(u);
    } else {
      roots.push(u);
    }
  });
  return roots;
}

export function fullName(
  p: Pick<Person, "last_name" | "first_name" | "patronymic">,
): string {
  return [p.last_name, p.first_name, p.patronymic].filter(Boolean).join(" ");
}

// ── API calls ──────────────────────────────────────────────────────────────────

const BASE = "/handbook";
export interface Event {
  id: string;
  person_id?: string;
  org_unit_id?: string;
  country_id?: string;
  title: string;
  event_type: string;
  date: string;
  location?: string;
  description?: string;
  participants: string[];
  source_url?: string;
  article_id?: string;
  generated_news_id?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}
export interface EventCreate {
  person_id?: string;
  org_unit_id?: string;
  country_id?: string;
  title: string;
  event_type: string;
  date: string;
  location?: string;
  description?: string;
  participants?: string[];
  source_url?: string;
  article_id?: string;
  generated_news_id?: string;
}
// Оновлений NewsLink з excerpt
export interface NewsLinkWithExcerpt extends NewsLink {
  excerpt?: string; // виділений фрагмент тексту статті
}
export const handbookApi = {
  // Countries
  listCountries: async (params?: {
    q?: string;
    page?: number;
    page_size?: number;
  }) => {
    const { data } = await client.get<PaginatedCountries>(`${BASE}/countries`, {
      params,
    });
    return data;
  },
  getPerson: async (id: string) => {
    const { data } = await client.get<Person>(`${BASE}/persons/${id}`);
    return data;
  },
  getPersonEvents: async (personId: string): Promise<HandbookEvent[]> => {
    const res = await fetch(`/api/handbook/persons/${personId}/events`);
    if (!res.ok) throw new Error("Failed to load person events");
    return res.json();
  },

  /** Список заходів підрозділу */
  getOrgUnitEvents: async (orgUnitId: string): Promise<HandbookEvent[]> => {
    const res = await fetch(`/api/handbook/org-units/${orgUnitId}/events`);
    if (!res.ok) throw new Error("Failed to load org unit events");
    return res.json();
  },

  /** Список заходів країни */
  getCountryEvents: async (countryId: string): Promise<HandbookEvent[]> => {
    const res = await fetch(`/api/handbook/countries/${countryId}/events`);
    if (!res.ok) throw new Error("Failed to load country events");
    return res.json();
  },

  /** Створити захід */
  createEvent: async (
    payload: EventCreatePayload,
    editor = "user",
  ): Promise<HandbookEvent> => {
    const res = await fetch("/api/handbook/events", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Changed-By": editor,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail ?? "Failed to create event");
    }
    return res.json();
  },

  /** Оновити захід */
  updateEvent: async (
    eventId: string,
    payload: Partial<EventCreatePayload>,
  ): Promise<HandbookEvent> => {
    const res = await fetch(`/api/handbook/events/${eventId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail ?? "Failed to update event");
    }
    return res.json();
  },

  /** Видалити захід */
  deleteEvent: async (eventId: string): Promise<void> => {
    const res = await fetch(`/api/handbook/events/${eventId}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete event");
  },

  getArticleEvents: async (articleId: string) => {
    const { data } = await client.get<Event[]>(
      `${BASE}/articles/${articleId}/events`,
    );
    return data;
  },

  getCountry: async (id: string) => {
    const { data } = await client.get<CountryDetail>(`${BASE}/countries/${id}`);
    return data;
  },
  createCountry: async (body: Partial<Country>, changedBy = "user") => {
    const { data } = await client.post<Country>(`${BASE}/countries`, body, {
      headers: { "X-Changed-By": changedBy },
    });
    return data;
  },
  getLinksForGeneratedNews: async (generatedNewsId: string) => {
    const { data } = await client.get<NewsLink[]>(
      `${BASE}/news-links/generated-news/${generatedNewsId}`,
    );
    return data;
  },
  updateCountry: async (
    id: string,
    body: Partial<Country>,
    changedBy = "user",
  ) => {
    const { data } = await client.patch<Country>(
      `${BASE}/countries/${id}`,
      body,
      {
        headers: { "X-Changed-By": changedBy },
      },
    );
    return data;
  },
  deleteCountry: async (id: string, changedBy = "user") => {
    await client.delete(`${BASE}/countries/${id}`, {
      headers: { "X-Changed-By": changedBy },
    });
  },

  // Org Units
  getOrgTree: async (countryId: string) => {
    const { data } = await client.get<OrgUnit[]>(
      `${BASE}/countries/${countryId}/org-units`,
    );
    return data;
  },
  createOrgUnit: async (body: Partial<OrgUnit>, changedBy = "user") => {
    const { data } = await client.post<OrgUnit>(`${BASE}/org-units`, body, {
      headers: { "X-Changed-By": changedBy },
    });
    return data;
  },
  updateOrgUnit: async (
    id: string,
    body: Partial<OrgUnit>,
    changedBy = "user",
  ) => {
    const { data } = await client.patch<OrgUnit>(
      `${BASE}/org-units/${id}`,
      body,
      {
        headers: { "X-Changed-By": changedBy },
      },
    );
    return data;
  },
  moveOrgUnit: async (
    id: string,
    newParentId: string | null,
    changedBy = "user",
  ) => {
    const { data } = await client.post<OrgUnit>(
      `${BASE}/org-units/${id}/move`,
      null,
      {
        params: { new_parent_id: newParentId },
        headers: { "X-Changed-By": changedBy },
      },
    );
    return data;
  },
  deleteOrgUnit: async (id: string, changedBy = "user") => {
    await client.delete(`${BASE}/org-units/${id}`, {
      headers: { "X-Changed-By": changedBy },
    });
  },

  // Persons
  listPersons: async (countryId: string) => {
    const { data } = await client.get<Person[]>(
      `${BASE}/countries/${countryId}/persons`,
    );
    return data;
  },
  createPerson: async (body: Partial<Person>, changedBy = "user") => {
    const { data } = await client.post<Person>(`${BASE}/persons`, body, {
      headers: { "X-Changed-By": changedBy },
    });
    return data;
  },
  updatePerson: async (
    id: string,
    body: Partial<Person>,
    changedBy = "user",
  ) => {
    const { data } = await client.patch<Person>(`${BASE}/persons/${id}`, body, {
      headers: { "X-Changed-By": changedBy },
    });
    return data;
  },
  deletePerson: async (id: string, changedBy = "user") => {
    await client.delete(`${BASE}/persons/${id}`, {
      headers: { "X-Changed-By": changedBy },
    });
  },

  // News Links
  createNewsLink: async (
    body: Partial<NewsLinkWithExcerpt> & { excerpt?: string },
    changedBy = "user",
  ) => {
    const { data } = await client.post<NewsLinkWithExcerpt>(
      `${BASE}/news-links`,
      body,
      {
        headers: { "X-Changed-By": changedBy },
      },
    );
    return data;
  },
  getLinksForArticle: async (articleId: string) => {
    const { data } = await client.get<NewsLink[]>(
      `${BASE}/news-links/article/${articleId}`,
    );
    return data;
  },
  getLinksForEntity: async (entityType: string, entityId: string) => {
    const { data } = await client.get<NewsLink[]>(
      `${BASE}/news-links/${entityType}/${entityId}`,
    );
    return data;
  },
  deleteNewsLink: async (linkId: string) => {
    await client.delete(`${BASE}/news-links/${linkId}`);
  },

  // Search
  search: async (q: string) => {
    const { data } = await client.get<{
      query: string;
      total: number;
      items: SearchResult[];
    }>(`${BASE}/search`, { params: { q } });
    return data;
  },
};
