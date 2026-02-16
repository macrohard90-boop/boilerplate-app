"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../lib/api";
import { useToast } from "../../../components/Toast";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface MetaOverride {
  id: string;
  path: string;
  title: string;
  description: string;
  created_at: string;
}

interface SEOConfig {
  site_name: string;
  default_og_image: string;
  domain: string;
  sitemap_cache_ttl: number;
}

export default function AdminSeoPage() {
  const { showToast } = useToast();
  const [overrides, setOverrides] = useState<MetaOverride[]>([]);
  const [config, setConfig] = useState<SEOConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);

  async function fetchData() {
    try {
      const [meta, cfg] = await Promise.all([
        apiFetch<{ items: MetaOverride[] }>("/seo/admin/seo/meta").catch(() => ({ items: [] })),
        apiFetch<SEOConfig>("/seo/admin/seo/config").catch(() => null),
      ]);
      setOverrides(meta.items || []);
      setConfig(cfg);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { fetchData(); }, []);

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      await apiFetch("/seo/admin/seo/sitemap/regenerate", { method: "POST" });
      showToast("Sitemap cache invalidated", "success");
    } catch (e) {
      const err = e as ApiError;
      showToast(err.message || "Failed", "error");
    }
    setRegenerating(false);
  }

  async function handleDeleteOverride(path: string) {
    try {
      await apiFetch(`/seo/admin/seo/meta/${path}`, { method: "DELETE" });
      showToast("Override removed", "success");
      fetchData();
    } catch {
      showToast("Failed to remove", "error");
    }
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">SEO Management</span>
      </h1>

      {/* Config */}
      {config && (
        <div className="glass rounded-xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Configuration</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-text-muted">Site name</p>
              <p className="text-text-primary">{config.site_name}</p>
            </div>
            <div>
              <p className="text-text-muted">Domain</p>
              <p className="text-text-primary">{config.domain}</p>
            </div>
            <div>
              <p className="text-text-muted">OG Image</p>
              <p className="text-text-primary text-xs font-mono">{config.default_og_image}</p>
            </div>
            <div>
              <p className="text-text-muted">Sitemap TTL</p>
              <p className="text-text-primary">{config.sitemap_cache_ttl}s</p>
            </div>
          </div>
        </div>
      )}

      {/* Sitemap */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-2">Sitemap</h2>
        <p className="text-sm text-text-secondary mb-4">Regenerate the cached sitemap.xml</p>
        <button onClick={handleRegenerate} disabled={regenerating} className="btn-secondary text-sm disabled:opacity-50">
          {regenerating ? "Regenerating..." : "Regenerate Sitemap"}
        </button>
      </div>

      {/* Meta overrides */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Meta Tag Overrides</h2>
        {overrides.length === 0 ? (
          <p className="text-sm text-text-muted">No custom meta overrides set</p>
        ) : (
          <div className="space-y-3">
            {overrides.map((o) => (
              <div key={o.id} className="flex items-center justify-between py-2 border-b border-glass-border/50 last:border-0">
                <div>
                  <p className="text-sm font-mono text-accent-blue">/{o.path}</p>
                  <p className="text-xs text-text-muted">{o.title}</p>
                </div>
                <button onClick={() => handleDeleteOverride(o.path)} className="text-text-muted hover:text-accent-pink transition-colors text-xs">
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
