import type { paths } from "@bagodi/api-client";

type CategoryItem = paths["/api/v1/catalog/categories"]["get"]["responses"][200]["content"]["application/json"][number];

interface CategoryNavProps {
  categories: CategoryItem[];
  selectedCategoryId: string | null;
  onSelectCategory: (id: string | null) => void;
  loading: boolean;
}

export function CategoryNav({
  categories,
  selectedCategoryId,
  onSelectCategory,
  loading,
}: CategoryNavProps) {
  return (
    <nav className="category-nav-bar" aria-label="Product categories">
      <div className="category-nav-inner">
        <button
          type="button"
          className={`category-pill ${selectedCategoryId === null ? "active" : ""}`}
          onClick={() => onSelectCategory(null)}
        >
          All Items
        </button>

        {loading ? (
          <>
            <div className="skeleton skeleton-pill" />
            <div className="skeleton skeleton-pill" />
            <div className="skeleton skeleton-pill" />
            <div className="skeleton skeleton-pill" />
          </>
        ) : (
          categories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={`category-pill ${selectedCategoryId === category.id ? "active" : ""}`}
              onClick={() => onSelectCategory(category.id)}
            >
              {category.name}
            </button>
          ))
        )}
      </div>
    </nav>
  );
}
