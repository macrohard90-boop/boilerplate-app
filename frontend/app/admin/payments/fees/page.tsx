"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../../lib/api";

interface FeeTier {
  id: string;
  name: string;
  min_volume: number;
  max_volume: number | null;
  fee_percent: number;
  fee_flat: number;
  sort_order: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

interface TierForm {
  name: string;
  min_volume: string;
  max_volume: string;
  fee_percent: string;
  fee_flat: string;
  sort_order: string;
}

const emptyForm: TierForm = {
  name: "",
  min_volume: "0",
  max_volume: "",
  fee_percent: "",
  fee_flat: "0",
  sort_order: "0",
};

function formatDollars(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
}

export default function AdminFeeTiersPage() {
  const [tiers, setTiers] = useState<FeeTier[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingTier, setEditingTier] = useState<FeeTier | null>(null);
  const [form, setForm] = useState<TierForm>({ ...emptyForm });

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function loadTiers() {
    try {
      const data = await apiFetch<FeeTier[]>("/ecommerce/admin/fee-tiers");
      setTiers(data);
    } catch {
      setMessage({ type: "error", text: "Failed to load fee tiers." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTiers();
  }, []);

  function openCreate() {
    setEditingTier(null);
    setForm({ ...emptyForm, sort_order: String(tiers.length + 1) });
    setShowModal(true);
    setMessage(null);
  }

  function openEdit(tier: FeeTier) {
    setEditingTier(tier);
    setForm({
      name: tier.name,
      min_volume: String(tier.min_volume),
      max_volume: tier.max_volume !== null ? String(tier.max_volume) : "",
      fee_percent: String(tier.fee_percent),
      fee_flat: String(tier.fee_flat),
      sort_order: String(tier.sort_order),
    });
    setShowModal(true);
    setMessage(null);
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    const payload = {
      name: form.name,
      min_volume: parseInt(form.min_volume) || 0,
      max_volume: form.max_volume ? parseInt(form.max_volume) : null,
      fee_percent: parseFloat(form.fee_percent) || 0,
      fee_flat: parseInt(form.fee_flat) || 0,
      sort_order: parseInt(form.sort_order) || 0,
    };

    try {
      if (editingTier) {
        await apiFetch(`/ecommerce/admin/fee-tiers/${editingTier.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setMessage({ type: "success", text: "Fee tier updated." });
      } else {
        await apiFetch("/ecommerce/admin/fee-tiers", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setMessage({ type: "success", text: "Fee tier created." });
      }
      setShowModal(false);
      await loadTiers();
    } catch {
      setMessage({ type: "error", text: "Failed to save fee tier." });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    setSaving(true);
    setMessage(null);
    try {
      await apiFetch(`/ecommerce/admin/fee-tiers/${id}`, { method: "DELETE" });
      setDeletingId(null);
      setMessage({ type: "success", text: "Fee tier deleted." });
      await loadTiers();
    } catch {
      setMessage({ type: "error", text: "Failed to delete fee tier." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl font-bold">
            <span className="gradient-text">Platform Fee Tiers</span>
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Volume-based fee schedule applied to merchant transactions.
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary px-4 py-1.5 rounded-lg text-sm">
          + Add Tier
        </button>
      </div>

      <div className="glass rounded-xl p-4 mb-6">
        <p className="text-xs text-text-muted">
          Fees are matched based on a merchant&apos;s aggregate sales volume. Each transaction incurs
          a <span className="text-text-secondary font-medium">percentage fee</span> plus an optional{" "}
          <span className="text-text-secondary font-medium">flat fee</span> (in cents). Merchants
          on higher volume tiers get lower rates. Per-merchant overrides can be configured separately.
        </p>
      </div>

      {message && (
        <div
          className={`mb-6 p-3 rounded-lg text-sm ${
            message.type === "success"
              ? "bg-green-500/10 border border-green-500/20 text-green-400"
              : "bg-red-500/10 border border-red-500/20 text-red-400"
          }`}
        >
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="text-center py-20 text-text-muted">Loading...</div>
      ) : tiers.length === 0 ? (
        <div className="text-center py-20 text-text-muted">
          <p className="text-lg mb-2">No fee tiers configured</p>
          <p className="text-sm">Add your first tier to start collecting platform fees.</p>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Tier Name</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Volume Range</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Fee %</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Flat Fee</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Order</th>
                <th className="text-right text-xs font-medium text-text-muted px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tiers.map((tier) => (
                <tr key={tier.id} className="border-b border-glass-border/50 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-sm font-medium text-text-primary">{tier.name}</td>
                  <td className="px-4 py-3 text-sm text-text-secondary">
                    {formatDollars(tier.min_volume)}
                    {" — "}
                    {tier.max_volume !== null ? formatDollars(tier.max_volume) : "Unlimited"}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-secondary">{tier.fee_percent}%</td>
                  <td className="px-4 py-3 text-sm text-text-secondary">
                    {tier.fee_flat > 0 ? formatDollars(tier.fee_flat) : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-muted">{tier.sort_order}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => openEdit(tier)}
                        className="text-xs text-accent-blue hover:text-accent-blue/80 transition-colors"
                      >
                        Edit
                      </button>
                      {deletingId === tier.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleDelete(tier.id)}
                            disabled={saving}
                            className="text-xs text-red-400 hover:text-red-300"
                          >
                            Confirm
                          </button>
                          <button
                            onClick={() => setDeletingId(null)}
                            className="text-xs text-text-muted hover:text-text-primary"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeletingId(tier.id)}
                          className="text-xs text-red-400/70 hover:text-red-400 transition-colors"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="glass rounded-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-text-primary mb-4">
              {editingTier ? "Edit Fee Tier" : "Add Fee Tier"}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-text-secondary mb-1">Tier Name</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Starter, Growth, Enterprise"
                  className="input-glass text-sm w-full"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Min Volume (cents)</label>
                  <input
                    type="number"
                    value={form.min_volume}
                    onChange={(e) => setForm({ ...form, min_volume: e.target.value })}
                    className="input-glass text-sm w-full"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">
                    {formatDollars(parseInt(form.min_volume) || 0)}
                  </p>
                </div>
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Max Volume (cents)</label>
                  <input
                    type="number"
                    value={form.max_volume}
                    onChange={(e) => setForm({ ...form, max_volume: e.target.value })}
                    placeholder="Empty = unlimited"
                    className="input-glass text-sm w-full"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">
                    {form.max_volume ? formatDollars(parseInt(form.max_volume) || 0) : "Unlimited"}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Fee Percent (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.fee_percent}
                    onChange={(e) => setForm({ ...form, fee_percent: e.target.value })}
                    placeholder="e.g. 15.00"
                    className="input-glass text-sm w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Flat Fee (cents)</label>
                  <input
                    type="number"
                    value={form.fee_flat}
                    onChange={(e) => setForm({ ...form, fee_flat: e.target.value })}
                    placeholder="e.g. 30 = $0.30"
                    className="input-glass text-sm w-full"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">
                    {formatDollars(parseInt(form.fee_flat) || 0)}
                  </p>
                </div>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Sort Order</label>
                <input
                  type="number"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                  className="input-glass text-sm w-full"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="btn-secondary text-sm flex-1"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !form.name || !form.fee_percent}
                className="btn-primary text-sm flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? "Saving..." : editingTier ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
