from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import CategoryIn, CategoryOut, ProductIn, ProductOut, ProductPatch
from api.security import require_staff
from shop.models import Category, Product

router = APIRouter(tags=["catálogo"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories():
    return list(Category.objects.all())


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
def create_category(data: CategoryIn):
    if Category.objects.filter(slug=data.slug).exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug já existe")
    return Category.objects.create(**data.model_dump())


@router.get("/products", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(None, description="Busca por nome"),
    category: str | None = Query(None, description="Slug da categoria"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    qs = Product.objects.filter(is_active=True).select_related("category")
    if q:
        qs = qs.filter(name__icontains=q)
    if category:
        qs = qs.filter(category__slug=category)
    return list(qs[offset : offset + limit])


@router.get("/products/{slug}", response_model=ProductOut)
def get_product(slug: str):
    product = Product.objects.select_related("category").filter(slug=slug, is_active=True).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    return product


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
def create_product(data: ProductIn):
    if not Category.objects.filter(pk=data.category_id).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoria não encontrada")
    if Product.objects.filter(slug=data.slug).exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug já existe")
    product = Product.objects.create(**data.model_dump())
    return Product.objects.select_related("category").get(pk=product.pk)


@router.patch(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_staff)],
)
def update_product(product_id: int, data: ProductPatch):
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.save()
    return Product.objects.select_related("category").get(pk=product.pk)
