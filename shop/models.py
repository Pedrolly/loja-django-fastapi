import os
import uuid
from decimal import Decimal

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def product_image_path(instance, filename):
    """Nome aleatório: evita colisões, cache velho e nomes adivinháveis."""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"products/{uuid.uuid4().hex}{ext}"


def validate_image_size(file):
    if file.size > settings.MAX_IMAGE_BYTES:
        limit_mb = settings.MAX_IMAGE_BYTES // (1024 * 1024)
        raise ValidationError(f"A imagem deve ter no máximo {limit_mb} MB.")

class Category(models.Model):
    name = models.CharField("nome", max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="categoria"
    )
    name = models.CharField("nome", max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField("descrição", blank=True)
    price = models.DecimalField("preço", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField("estoque", default=0)
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Pago"
        SHIPPED = "shipped", "Enviado"
        CANCELED = "canceled", "Cancelado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="cliente"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.pk}"

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity
