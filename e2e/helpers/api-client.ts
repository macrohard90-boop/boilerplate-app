/**
 * Admin API client — used by validation tests to query event registry and metrics.
 */

import { APIRequestContext } from "@playwright/test";

export interface EventDefinition {
  name: string;
  fire_count_30d: number;
  last_fired: string | null;
  is_enabled: boolean;
  category: string;
}

export interface MetricResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  cached: boolean;
}

export interface SavedMetric {
  id: string;
  name: string;
  sql_query: string;
  is_audience: boolean;
  preset_key: string | null;
}

export class AdminApiClient {
  private request: APIRequestContext;
  private token: string;

  constructor(request: APIRequestContext, token: string) {
    this.request = request;
    this.token = token;
  }

  private headers() {
    return {
      Authorization: `Bearer ${this.token}`,
      "Content-Type": "application/json",
    };
  }

  /** Login as admin and return a client instance. */
  static async login(
    request: APIRequestContext,
    baseUrl: string,
    email: string,
    password: string,
  ): Promise<AdminApiClient> {
    const res = await request.post(`${baseUrl}/api/auth/login`, {
      data: { email, password },
    });
    if (!res.ok()) {
      throw new Error(`Admin login failed: ${res.status()} ${await res.text()}`);
    }
    const data = await res.json();
    return new AdminApiClient(request, data.access_token);
  }

  /** Get all event definitions with 30-day fire counts. */
  async getEventDefinitions(): Promise<EventDefinition[]> {
    const res = await this.request.get("/api/tracking/admin/events", {
      headers: this.headers(),
    });
    if (!res.ok()) return [];
    const data = await res.json();
    return data.items || data;
  }

  /** Get all saved metrics. */
  async getSavedMetrics(): Promise<SavedMetric[]> {
    const res = await this.request.get("/api/tracking/admin/metrics", {
      headers: this.headers(),
    });
    if (!res.ok()) return [];
    const data = await res.json();
    return data.items || data;
  }

  /** Run a specific saved metric by ID. */
  async runMetric(metricId: string): Promise<MetricResult | null> {
    const res = await this.request.post(
      `/api/tracking/admin/metrics/${metricId}/run`,
      { headers: this.headers() },
    );
    if (!res.ok()) return null;
    return await res.json();
  }
}
