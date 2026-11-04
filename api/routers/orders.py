from typing import Optional

from django.db import transaction
from django.db.models import F
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.schemas import OrderIn, OrderOut, OrderStatusIn
from api.security import get_current_user
from shop.models import Order, OrderItem, Product

router = APIRouter(prefix="/orders", tags=["pedidos"])

# Transições permitidas: estado atual -> possíveis próximos estados
ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PAID, Order.Status.CANCELED},
    Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELED},
    Order.Status.SHIPPED: set(),
    Order.Status.CANCELED: set(),
}

def require_admin(user=Depends(get_current_user)):
    # Se você já tem uma dependência de admin em api/security.py, use ela no lugar.
    if not user.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores")
    return user

def serialize(order: Order) -> OrderOut:
    items = [
        {
            "product_id": i.product_id,
            "product_name": i.product.name,
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "subtotal": i.subtotal,
        }
        for i in order.items.select_related("product")
    ]
    return OrderOut(
        id=order.pk,
        status=order.status,
        created_at=order.created_at,
        total=sum(i["subtotal"] for i in items),
        items=items,
    )

def _restore_stock(order: Order) -> None:
    """Devolve ao estoque os itens de um pedido cancelado (chamar dentro de atomic)."""
    items = list(order.items.all())
    # Trava os produtos em ordem fixa (por pk) para evitar deadlock entre transações
    list(
        Product.objects.select_for_update()
        .filter(pk__in=[i.product_id for i in items])
        .order_by("pk")
    )
    for item in items:
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)


def change_status(order_id: int, new_status: str, owner=None) -> Order:
    """Muda o status validando a transição. Se `owner` for passado, só acha pedidos dele."""
    with transaction.atomic():
        qs = Order.objects.select_for_update().filter(pk=order_id)
        if owner is not None:
            qs = qs.filter(user=owner)
        order = qs.first()
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")

        if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Não é possível mudar o pedido de '{order.status}' para '{new_status}'",
            )

        if new_status == Order.Status.CANCELED:
            _restore_stock(order)

        order.status = new_status
        order.save(update_fields=["status"])
    return order


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderIn, user=Depends(get_current_user)):
    # Agrupa itens repetidos do mesmo produto
    wanted: dict[int, int] = {}
    for item in data.items:
        wanted[item.product_id] = wanted.get(item.product_id, 0) + item.quantity

    with transaction.atomic():
        # select_for_update evita vender o mesmo estoque duas vezes (concorrência)
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(
                pk__in=wanted.keys(), is_active=True
            )
        }
        for product_id, qty in wanted.items():
            product = products.get(product_id)
            if product is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"Produto {product_id} não encontrado"
                )
            if product.stock < qty:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Estoque insuficiente para '{product.name}' (disponível: {product.stock})",
                )

        order = Order.objects.create(user=user)
        for product_id, qty in wanted.items():
            product = products[product_id]
            OrderItem.objects.create(
                order=order, product=product, quantity=qty, unit_price=product.price
            )
            product.stock -= qty
            product.save(update_fields=["stock"])

    return serialize(order)



@router.get("", response_model=list[OrderOut])
def my_orders(user=Depends(get_current_user)):
    return [serialize(o) for o in Order.objects.filter(user=user)]

# Rota de admin: listar todos os pedidos (com filtro opcional por status)
@router.get("/admin/all", response_model=list[OrderOut])
def all_orders(
    status_filter: Optional[Order.Status] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin=Depends(require_admin),
):
    qs = Order.objects.all()
    if status_filter:
        qs = qs.filter(status=status_filter)
    return [serialize(o) for o in qs[offset : offset + limit]]

@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user=Depends(get_current_user)):
    order = Order.objects.filter(pk=order_id, user=user).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    return serialize(order)

# Cliente cancela o próprio pedido (somente se ainda estiver pendente)
@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, user=Depends(get_current_user)):
    order = Order.objects.filter(pk=order_id, user=user).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    if order.status != Order.Status.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Só é possível cancelar pedidos pendentes. Fale com o suporte.",
        )
    return serialize(change_status(order_id, Order.Status.CANCELED, owner=user))

# Admin altera o status (pago, enviado, cancelado)
@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(order_id: int, data: OrderStatusIn, _admin=Depends(require_admin)):
    return serialize(change_status(order_id, data.status))

