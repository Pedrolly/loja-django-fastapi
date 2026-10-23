import io

from django.conf import settings
from django.core.files.base import ContentFile
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from api.schemas import CategoryIn, CategoryOut, ProductIn, ProductOut, ProductPatch
from api.security import require_staff
from shop.models import Category, Product

router = APIRouter(tags=["catálogo"])

# formato detectado pelo Pillow -> extensão salva em disco
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def process_image(data: bytes) -> tuple[bytes, str]:
    """Valida de verdade (não confia no nome/Content-Type), reduz e recodifica.

    Recodificar descarta metadados (EXIF/GPS) e qualquer lixo escondido no arquivo.
    """
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # checa a integridade; depois disso o objeto não serve mais
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in ALLOWED_FORMATS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use uma imagem JPEG, PNG ou WebP"
            )
        img = ImageOps.exif_transpose(img)  # respeita a rotação da câmera
        size = settings.IMAGE_MAX_DIMENSION
        img.thumbnail((size, size))
        if fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        if fmt in ("JPEG", "WEBP"):
            img.save(out, format=fmt, quality=85)
        else:
            img.save(out, format=fmt, optimize=True)
        return out.getvalue(), ALLOWED_FORMATS[fmt]
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O arquivo não é uma imagem válida")
    
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
@router.post(
    "/products/{product_id}/image",
    response_model=ProductOut,
    dependencies=[Depends(require_staff)],
    summary="Envia (ou troca) a imagem do produto",
)
def upload_product_image(product_id: int, file: UploadFile = File(...)):
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")

    # lê no máximo limite+1 bytes: se passar, rejeita sem carregar um arquivo gigante
    limit = settings.MAX_IMAGE_BYTES
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            413,
            f"Imagem maior que {limit // (1024 * 1024)} MB",
        )

    content, ext = process_image(data)

    if product.image:
        product.image.delete(save=False)  # apaga o arquivo antigo do disco
    product.image.save(f"produto{ext}", ContentFile(content), save=True)
    return Product.objects.select_related("category").get(pk=product.pk)


@router.delete(
    "/products/{product_id}/image",
    response_model=ProductOut,
    dependencies=[Depends(require_staff)],
    summary="Remove a imagem do produto",
)
def delete_product_image(product_id: int):
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    if product.image:
        product.image.delete(save=True)
    return Product.objects.select_related("category").get(pk=product.pk)