"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, apiUpload } from "../../lib/api";

interface ProductImage {
  id: string;
  product_id: string;
  url: string;
  alt_text: string | null;
  sort_order: number;
  is_primary: boolean;
}

interface ImageUploaderProps {
  productId: string;
}

export default function ImageUploader({ productId }: ImageUploaderProps) {
  const [images, setImages] = useState<ProductImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const fetchImages = useCallback(async () => {
    try {
      const data = await apiFetch<ProductImage[]>(
        `/ecommerce/products/${productId}/images`
      );
      setImages(data);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, [productId]);

  useEffect(() => {
    fetchImages();
  }, [fetchImages]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    if (images.length + files.length > 8) {
      alert("Maximum 8 images per product");
      return;
    }

    setUploading(true);
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        await apiUpload(
          `/ecommerce/products/${productId}/images/upload`,
          formData
        );
      } catch {
        /* ignore individual failures */
      }
    }
    await fetchImages();
    setUploading(false);
  };

  const handleDelete = async (imageId: string) => {
    try {
      await apiFetch(`/ecommerce/products/${productId}/images/${imageId}`, {
        method: "DELETE",
      });
      setImages((prev) => prev.filter((img) => img.id !== imageId));
    } catch {
      /* ignore */
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text-primary">
          Images{" "}
          <span className="text-text-muted font-normal text-sm">
            ({images.length}/8)
          </span>
        </h3>
      </div>

      {/* Upload area */}
      <div
        className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer mb-4 ${
          dragOver
            ? "border-accent-blue bg-accent-blue/10"
            : "border-glass-border hover:border-text-muted"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => {
          const input = document.createElement("input");
          input.type = "file";
          input.accept = "image/jpeg,image/png,image/webp,image/gif";
          input.multiple = true;
          input.onchange = () => handleUpload(input.files);
          input.click();
        }}
      >
        {uploading ? (
          <p className="text-text-muted text-sm">Uploading...</p>
        ) : (
          <>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 mx-auto text-text-muted mb-2"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <p className="text-text-muted text-sm">
              Drop images here or click to upload
            </p>
            <p className="text-text-muted text-xs mt-1">
              JPEG, PNG, WebP, or GIF. Max 5 MB each.
            </p>
          </>
        )}
      </div>

      {/* Image grid */}
      {loading ? (
        <p className="text-text-muted text-sm">Loading images...</p>
      ) : images.length === 0 ? (
        <p className="text-text-secondary text-sm text-center">
          No images uploaded yet.
        </p>
      ) : (
        <div className="grid grid-cols-4 gap-3">
          {images.map((img) => (
            <div
              key={img.id}
              className="relative group glass rounded-lg overflow-hidden aspect-square"
            >
              <img
                src={img.url}
                alt={img.alt_text || "Product image"}
                className="w-full h-full object-cover"
              />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(img.id);
                }}
                className="absolute top-1 right-1 bg-black/60 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
              >
                X
              </button>
              {img.is_primary && (
                <span className="absolute bottom-1 left-1 bg-accent-blue/80 text-white text-xs px-1.5 py-0.5 rounded">
                  Primary
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
