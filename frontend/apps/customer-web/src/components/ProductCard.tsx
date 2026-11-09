import type { MouseEvent } from "react";
import { Plus, Tag } from "lucide-react";
import type { paths } from "@bagodi/api-client";

type ProductSummary = paths["/api/v1/catalog/products"]["get"]["responses"][200]["content"]["application/json"][number];

interface ProductCardProps {
  product: ProductSummary;
  onClick: (product: ProductSummary) => void;
  onAddToCart: (product: ProductSummary, variantId: string) => void;
}

export function ProductCard({ product, onClick, onAddToCart }: ProductCardProps) {
  const primaryVariant = product.variants?.[0];
  const primaryImage = product.images?.[0]?.url;

  const displayPrice = primaryVariant ? parseFloat(primaryVariant.base_price) : 0;
  const regularPrice = primaryVariant?.mrp ? parseFloat(primaryVariant.mrp) : null;
  const hasDiscount = regularPrice && regularPrice > displayPrice;
  const discountPercent = hasDiscount ? Math.round(((regularPrice - displayPrice) / regularPrice) * 100) : 0;

  const variantLabel =
    primaryVariant?.size ||
    (primaryVariant?.attributes ? Object.values(primaryVariant.attributes).join(" • ") : primaryVariant?.name);

  const handleAddClick = (e: MouseEvent) => {
    e.stopPropagation();
    if (primaryVariant) {
      onAddToCart(product, primaryVariant.id);
    }
  };

  return (
    <article className="product-card" onClick={() => onClick(product)}>
      <div className="product-image-container">
        {primaryImage ? (
          <img
            src={primaryImage}
            alt={product.name}
            className="product-image"
            loading="lazy"
          />
        ) : (
          <div className="product-image-placeholder">
            <Tag size={28} />
            <span>Bagodi Fresh</span>
          </div>
        )}

        {hasDiscount && (
          <span className="product-badge-discount">
            {discountPercent}% OFF
          </span>
        )}
      </div>

      <h3 className="product-title" title={product.name}>
        {product.name}
      </h3>

      <div className="product-variant-meta">
        {variantLabel || "Standard Pack"}
      </div>

      <div className="product-card-footer">
        <div className="price-container">
          <span className="current-price">
            ₹{displayPrice.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
          </span>
          {hasDiscount && (
            <span className="regular-price">
              ₹{regularPrice.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
            </span>
          )}
        </div>

        <button
          type="button"
          className="btn-add-item"
          onClick={handleAddClick}
          aria-label={`Add ${product.name} to cart`}
        >
          <Plus size={14} />
          Add
        </button>
      </div>
    </article>
  );
}
