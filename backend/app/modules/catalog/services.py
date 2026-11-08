from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from app.modules.catalog.schemas import (
    BrandCreate,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductImageCreate,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
)


class CategoryService:
    @staticmethod
    async def create_category(db: AsyncSession, data: CategoryCreate, tenant_id: UUID | None = None) -> Category:
        query = select(Category).where(Category.slug == data.slug)
        if tenant_id:
            query = query.where(Category.tenant_id == tenant_id)
        else:
            query = query.where(Category.tenant_id.is_(None))

        existing = (await db.execute(query)).scalar_one_or_none()
        if existing:
            scope = f"merchant {tenant_id}" if tenant_id else "global catalog"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CATEGORY_SLUG_EXISTS", "message": f"Category slug '{data.slug}' already exists in {scope}."},
            )

        if data.parent_id:
            parent_stmt = select(Category).where(Category.id == data.parent_id)
            parent = (await db.execute(parent_stmt)).scalar_one_or_none()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "PARENT_CATEGORY_NOT_FOUND", "message": "Parent category not found."},
                )

        category = Category(
            tenant_id=tenant_id,
            parent_id=data.parent_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @staticmethod
    async def list_categories(
        db: AsyncSession, tenant_id: UUID | None = None, active_only: bool = False
    ) -> list[Category]:
        query = select(Category)
        if tenant_id:
            query = query.where(or_(Category.tenant_id.is_(None), Category.tenant_id == tenant_id))
        else:
            query = query.where(Category.tenant_id.is_(None))

        if active_only:
            query = query.where(Category.is_active.is_(True))

        query = query.order_by(Category.sort_order.asc(), Category.name.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_category_by_id(db: AsyncSession, category_id: UUID, tenant_id: UUID | None = None) -> Category:
        stmt = select(Category).where(Category.id == category_id)
        category = (await db.execute(stmt)).scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CATEGORY_NOT_FOUND", "message": "Category not found."},
            )

        if category.tenant_id and category.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CATEGORY_NOT_FOUND", "message": "Category not found."},
            )

        return category

    @staticmethod
    async def update_category(
        db: AsyncSession, category_id: UUID, data: CategoryUpdate, tenant_id: UUID | None = None
    ) -> Category:
        category = await CategoryService.get_category_by_id(db, category_id, tenant_id)
        if category.tenant_id is None and tenant_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "CANNOT_MODIFY_GLOBAL_CATEGORY", "message": "Merchants cannot modify platform master categories."},
            )

        if data.name is not None:
            category.name = data.name
        if data.parent_id is not None:
            category.parent_id = data.parent_id
        if data.description is not None:
            category.description = data.description
        if data.sort_order is not None:
            category.sort_order = data.sort_order
        if data.is_active is not None:
            category.is_active = data.is_active

        await db.commit()
        await db.refresh(category)
        return category


class BrandService:
    @staticmethod
    async def create_brand(db: AsyncSession, data: BrandCreate, tenant_id: UUID | None = None) -> Brand:
        query = select(Brand).where(Brand.slug == data.slug)
        if tenant_id:
            query = query.where(Brand.tenant_id == tenant_id)
        else:
            query = query.where(Brand.tenant_id.is_(None))

        existing = (await db.execute(query)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "BRAND_SLUG_EXISTS", "message": f"Brand slug '{data.slug}' already exists."},
            )

        brand = Brand(
            tenant_id=tenant_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            is_active=data.is_active,
        )
        db.add(brand)
        await db.commit()
        await db.refresh(brand)
        return brand

    @staticmethod
    async def list_brands(
        db: AsyncSession, tenant_id: UUID | None = None, active_only: bool = False
    ) -> list[Brand]:
        query = select(Brand)
        if tenant_id:
            query = query.where(or_(Brand.tenant_id.is_(None), Brand.tenant_id == tenant_id))
        else:
            query = query.where(Brand.tenant_id.is_(None))

        if active_only:
            query = query.where(Brand.is_active.is_(True))

        query = query.order_by(Brand.name.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_brand_by_id(db: AsyncSession, brand_id: UUID, tenant_id: UUID | None = None) -> Brand:
        stmt = select(Brand).where(Brand.id == brand_id)
        brand = (await db.execute(stmt)).scalar_one_or_none()
        if not brand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "BRAND_NOT_FOUND", "message": "Brand not found."},
            )
        if brand.tenant_id and brand.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "BRAND_NOT_FOUND", "message": "Brand not found."},
            )
        return brand


class ProductService:
    @staticmethod
    async def create_product(db: AsyncSession, tenant_id: UUID, data: ProductCreate) -> Product:
        # 1. Enforce product slug uniqueness per tenant
        slug_stmt = select(Product).where(Product.tenant_id == tenant_id, Product.slug == data.slug)
        existing_product = (await db.execute(slug_stmt)).scalar_one_or_none()
        if existing_product:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PRODUCT_SLUG_EXISTS", "message": f"Product slug '{data.slug}' already exists for this merchant."},
            )

        # 2. Verify category exists and is accessible
        await CategoryService.get_category_by_id(db, data.category_id, tenant_id)

        # 3. If brand provided, verify brand exists
        if data.brand_id:
            await BrandService.get_brand_by_id(db, data.brand_id, tenant_id)

        # 4. Pre-validate variant SKU & barcode uniqueness across tenant
        for variant_data in data.variants:
            sku_stmt = select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id, ProductVariant.sku == variant_data.sku
            )
            existing_sku = (await db.execute(sku_stmt)).scalar_one_or_none()
            if existing_sku:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "VARIANT_SKU_EXISTS", "message": f"Variant SKU '{variant_data.sku}' already exists for this merchant."},
                )

            if variant_data.barcode:
                barcode_stmt = select(ProductVariant).where(
                    ProductVariant.tenant_id == tenant_id, ProductVariant.barcode == variant_data.barcode
                )
                existing_barcode = (await db.execute(barcode_stmt)).scalar_one_or_none()
                if existing_barcode:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"code": "VARIANT_BARCODE_EXISTS", "message": f"Barcode '{variant_data.barcode}' is already assigned."},
                    )

        # 5. Create base product
        product = Product(
            tenant_id=tenant_id,
            category_id=data.category_id,
            brand_id=data.brand_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
            is_published=data.is_published,
        )
        db.add(product)
        await db.flush()

        # 6. Add variants
        for v in data.variants:
            variant = ProductVariant(
                tenant_id=tenant_id,
                product_id=product.id,
                sku=v.sku,
                barcode=v.barcode,
                name=v.name,
                size=v.size,
                color=v.color,
                attributes=v.attributes,
                mrp=v.mrp,
                base_price=v.base_price,
                status=v.status,
            )
            db.add(variant)

        # 7. Add images
        for img in data.images:
            image = ProductImage(
                tenant_id=tenant_id,
                product_id=product.id,
                variant_id=img.variant_id,
                url=img.url,
                alt_text=img.alt_text,
                sort_order=img.sort_order,
                is_primary=img.is_primary,
            )
            db.add(image)

        await db.commit()
        return await ProductService.get_merchant_product(db, tenant_id, product.id)

    @staticmethod
    async def get_merchant_product(db: AsyncSession, tenant_id: UUID, product_id: UUID) -> Product:
        stmt = (
            select(Product)
            .where(Product.tenant_id == tenant_id, Product.id == product_id)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
        product = (await db.execute(stmt)).scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found for this merchant."},
            )
        return product

    @staticmethod
    async def list_merchant_products(
        db: AsyncSession,
        tenant_id: UUID,
        category_id: UUID | None = None,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.tenant_id == tenant_id)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if status_filter:
            stmt = stmt.where(Product.status == status_filter)

        stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_merchant_product(
        db: AsyncSession, tenant_id: UUID, product_id: UUID, data: ProductUpdate
    ) -> Product:
        product = await ProductService.get_merchant_product(db, tenant_id, product_id)

        if data.category_id is not None:
            await CategoryService.get_category_by_id(db, data.category_id, tenant_id)
            product.category_id = data.category_id
        if data.brand_id is not None:
            await BrandService.get_brand_by_id(db, data.brand_id, tenant_id)
            product.brand_id = data.brand_id
        if data.name is not None:
            product.name = data.name
        if data.description is not None:
            product.description = data.description
        if data.status is not None:
            product.status = data.status
        if data.is_published is not None:
            product.is_published = data.is_published

        await db.commit()
        return await ProductService.get_merchant_product(db, tenant_id, product.id)

    @staticmethod
    async def add_variant(
        db: AsyncSession, tenant_id: UUID, product_id: UUID, data: ProductVariantCreate
    ) -> ProductVariant:
        await ProductService.get_merchant_product(db, tenant_id, product_id)

        sku_stmt = select(ProductVariant).where(
            ProductVariant.tenant_id == tenant_id, ProductVariant.sku == data.sku
        )
        if (await db.execute(sku_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "VARIANT_SKU_EXISTS", "message": f"Variant SKU '{data.sku}' already exists for this merchant."},
            )

        if data.barcode:
            barcode_stmt = select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id, ProductVariant.barcode == data.barcode
            )
            if (await db.execute(barcode_stmt)).scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "VARIANT_BARCODE_EXISTS", "message": f"Barcode '{data.barcode}' already exists for this merchant."},
                )

        variant = ProductVariant(
            tenant_id=tenant_id,
            product_id=product_id,
            sku=data.sku,
            barcode=data.barcode,
            name=data.name,
            size=data.size,
            color=data.color,
            attributes=data.attributes,
            mrp=data.mrp,
            base_price=data.base_price,
            status=data.status,
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)
        return variant

    @staticmethod
    async def update_variant(
        db: AsyncSession, tenant_id: UUID, variant_id: UUID, data: ProductVariantUpdate
    ) -> ProductVariant:
        stmt = select(ProductVariant).where(
            ProductVariant.tenant_id == tenant_id, ProductVariant.id == variant_id
        )
        variant = (await db.execute(stmt)).scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "VARIANT_NOT_FOUND", "message": "Product variant not found for this merchant."},
            )

        if data.barcode is not None and data.barcode != variant.barcode:
            barcode_stmt = select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id, ProductVariant.barcode == data.barcode
            )
            if (await db.execute(barcode_stmt)).scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "VARIANT_BARCODE_EXISTS", "message": f"Barcode '{data.barcode}' is already in use."},
                )
            variant.barcode = data.barcode

        if data.name is not None:
            variant.name = data.name
        if data.size is not None:
            variant.size = data.size
        if data.color is not None:
            variant.color = data.color
        if data.attributes is not None:
            variant.attributes = data.attributes
        if data.mrp is not None:
            variant.mrp = data.mrp
        if data.base_price is not None:
            variant.base_price = data.base_price
        if data.status is not None:
            variant.status = data.status

        await db.commit()
        await db.refresh(variant)
        return variant

    @staticmethod
    async def add_image(
        db: AsyncSession, tenant_id: UUID, product_id: UUID, data: ProductImageCreate
    ) -> ProductImage:
        await ProductService.get_merchant_product(db, tenant_id, product_id)
        image = ProductImage(
            tenant_id=tenant_id,
            product_id=product_id,
            variant_id=data.variant_id,
            url=data.url,
            alt_text=data.alt_text,
            sort_order=data.sort_order,
            is_primary=data.is_primary,
        )
        db.add(image)
        await db.commit()
        await db.refresh(image)
        return image

    @staticmethod
    async def list_public_products(
        db: AsyncSession,
        tenant_id: UUID | None = None,
        category_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.status == "active", Product.is_published.is_(True))
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
        if tenant_id:
            stmt = stmt.where(Product.tenant_id == tenant_id)
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search.strip()}%"))

        stmt = stmt.order_by(Product.name.asc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_public_product_by_slug(
        db: AsyncSession, slug: str, tenant_id: UUID | None = None
    ) -> Product:
        stmt = (
            select(Product)
            .where(
                Product.slug == slug,
                Product.status == "active",
                Product.is_published.is_(True),
            )
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
        if tenant_id:
            stmt = stmt.where(Product.tenant_id == tenant_id)

        product = (await db.execute(stmt)).scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": "Product is not available."},
            )
        return product

    @staticmethod
    async def lookup_by_barcode(
        db: AsyncSession, tenant_id: UUID, barcode: str
    ) -> tuple[ProductVariant, Product]:
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.tenant_id == tenant_id, ProductVariant.barcode == barcode)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.images),
                selectinload(ProductVariant.product).selectinload(Product.variants),
            )
        )
        variant = (await db.execute(stmt)).scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "BARCODE_NOT_FOUND", "message": f"No product variant found for barcode '{barcode}'."},
            )
        return variant, variant.product
