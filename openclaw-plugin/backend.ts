/**
 * HTTP backend adapter for SeekingContext REST API.
 *
 * Wraps the SeekingContext REST endpoints into a
 * simple interface that the openclaw plugin consumes.
 * All requests include the X-Namespace header for
 * cross-framework scope isolation.
 */

// ================================================================
// Types
// ================================================================

/** A stored memory item. */
export interface Memory {
  id: string;
  content: string;
  abstract: string;
  overview: string;
  category: string;
  user_id?: string | null;
  agent_id?: string | null;
  session_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  active_count: number;
}

/** Search result with relevance score. */
export interface SearchResult {
  id: string;
  score: number;
  vector_score: number;
  text_score: number;
  content: string;
  category: string;
  namespace?: string;
}

/** Input for storing a new memory. */
export interface StoreInput {
  content: string;
  category?: string;
  abstract?: string;
  overview?: string;
  metadata?: Record<string, unknown>;
}

/** Input for searching memories. */
export interface SearchInput {
  query: string;
  top_k?: number;
  category?: string;
  level?: number;
}

/** Input for updating a memory. */
export interface UpdateInput {
  content?: string;
  abstract?: string;
  overview?: string;
  metadata?: Record<string, unknown>;
}

// ================================================================
// Backend
// ================================================================

export class SeekingContextBackend {
  /** REST API base URL. */
  private readonly apiUrl: string;
  /** Namespace for scope isolation. */
  private readonly namespace: string;

  constructor(apiUrl: string, namespace: string) {
    // Strip trailing slash for consistent URL building
    this.apiUrl = apiUrl.replace(/\/+$/, "");
    this.namespace = namespace;
  }

  // -- helpers ------------------------------------------------

  /**
   * Build default headers with namespace and JSON content type.
   */
  private headers(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      "X-Namespace": this.namespace,
    };
  }

  /**
   * Execute a fetch request and parse JSON response.
   *
   * Throws on non-2xx status codes with the response
   * body included in the error message.
   */
  private async request<T>(
    path: string,
    init?: RequestInit,
  ): Promise<T> {
    const url = `${this.apiUrl}${path}`;
    const resp = await fetch(url, {
      ...init,
      headers: {
        ...this.headers(),
        ...(init?.headers as Record<string, string>),
      },
    });
    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      throw new Error(
        `SeekingContext API error ${resp.status}: ${body}`,
      );
    }
    return resp.json() as Promise<T>;
  }

  // -- CRUD ---------------------------------------------------

  /**
   * Store a new memory.
   *
   * Returns { id, status } on success.
   */
  async store(
    input: StoreInput,
  ): Promise<{ id: string; status: string }> {
    return this.request("/v1/memories", {
      method: "POST",
      body: JSON.stringify({
        content: input.content,
        category: input.category ?? "entities",
        abstract: input.abstract ?? "",
        overview: input.overview ?? "",
        metadata: input.metadata,
      }),
    });
  }

  /**
   * Search memories with hybrid vector + keyword matching.
   *
   * Returns ranked list of SearchResult objects.
   */
  async search(input: SearchInput): Promise<SearchResult[]> {
    return this.request("/v1/memories/search", {
      method: "POST",
      body: JSON.stringify({
        query: input.query,
        top_k: input.top_k ?? 5,
        category: input.category,
        level: input.level ?? 2,
      }),
    });
  }

  /**
   * Retrieve a single memory by ID.
   *
   * Returns null if not found (404).
   */
  async get(id: string): Promise<Memory | null> {
    try {
      return await this.request<Memory>(
        `/v1/memories/${encodeURIComponent(id)}`,
      );
    } catch (err) {
      if (
        err instanceof Error &&
        err.message.includes("404")
      ) {
        return null;
      }
      throw err;
    }
  }

  /**
   * Update an existing memory.
   *
   * Only provided fields in input are changed.
   */
  async update(
    id: string,
    input: UpdateInput,
  ): Promise<{ id: string; status: string }> {
    return this.request(
      `/v1/memories/${encodeURIComponent(id)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
    );
  }

  /**
   * Delete a memory by ID.
   *
   * Returns true on success, false if not found.
   */
  async remove(id: string): Promise<boolean> {
    try {
      await this.request(
        `/v1/memories/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      );
      return true;
    } catch (err) {
      if (
        err instanceof Error &&
        err.message.includes("404")
      ) {
        return false;
      }
      throw err;
    }
  }

  /**
   * List memories with optional filters.
   */
  async list(
    opts?: { category?: string; limit?: number },
  ): Promise<Memory[]> {
    const params = new URLSearchParams();
    if (opts?.category) {
      params.set("category", opts.category);
    }
    if (opts?.limit) {
      params.set("limit", String(opts.limit));
    }
    const qs = params.toString();
    const path = qs
      ? `/v1/memories?${qs}`
      : "/v1/memories";
    return this.request<Memory[]>(path);
  }

  /**
   * Health check — returns server status and memory count.
   */
  async status(): Promise<{
    status: string;
    version: string;
    memory_count: number;
    active_sessions: number;
  }> {
    return this.request("/v1/status");
  }
}
