"use client";

import { useState } from "react";

export interface CategoryFormData {
  name: string;
  parent_id: string | null;
  description: string;
  sort_order: number;
}

interface CategoryOption {
  id: string;
  name: string;
  parent_id: string | null;
}

interface CategoryFormProps {
  initial?: Partial<CategoryFormData> | null;
  onSubmit: (data: CategoryFormData) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  submitLabel?: string;
  categories?: CategoryOption[];
  /** ID of the category being edited (to exclude self + descendants from parent picker) */
  editingId?: string | null;
}

export default function CategoryForm({
  initial,
  onSubmit,
  onCancel,
  loading,
  submitLabel = "Save",
  categories = [],
  editingId,
}: CategoryFormProps) {
  const [name, setName] = useState(initial?.name || "");
  const [parentId, setParentId] = useState<string>(initial?.parent_id || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [sortOrder, setSortOrder] = useState(initial?.sort_order ?? 0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Exclude self and descendants from parent picker to prevent circular references
  const getDescendantIds = (id: string): string[] => {
    const result: string[] = [id];
    const children = categories.filter((c) => c.parent_id === id);
    for (const child of children) {
      result.push(...getDescendantIds(child.id));
    }
    return result;
  };

  const excludeIds = editingId ? new Set(getDescendantIds(editingId)) : new Set<string>();
  const parentOptions = categories.filter((c) => !excludeIds.has(c.id));

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Name is required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    await onSubmit({
      name: name.trim(),
      parent_id: parentId || null,
      description: description.trim(),
      sort_order: sortOrder,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Name */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Name *</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input-glass w-full"
          placeholder="Category name"
          disabled={loading}
        />
        {errors.name && <p className="text-accent-pink text-xs mt-1">{errors.name}</p>}
      </div>

      {/* Parent Category */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Parent Category</label>
        <select
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          className="input-glass w-full"
          disabled={loading}
        >
          <option value="">None (root category)</option>
          {parentOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.parent_id ? `  └ ${c.name}` : c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="input-glass w-full h-20 resize-none"
          placeholder="Optional description"
          disabled={loading}
        />
      </div>

      {/* Sort Order */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Sort Order</label>
        <input
          type="number"
          min="0"
          value={sortOrder}
          onChange={(e) => setSortOrder(parseInt(e.target.value, 10) || 0)}
          className="input-glass w-32"
          disabled={loading}
        />
        <p className="text-text-muted text-xs mt-1">Lower numbers appear first</p>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="btn-secondary px-4 py-2 rounded-lg text-sm"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="btn-primary px-4 py-2 rounded-lg text-sm"
          disabled={loading}
        >
          {loading ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
