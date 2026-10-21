from django.db import transaction
from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import OrderIn, OrderOut
from api.security import get_current_user
from shop.models import Order, OrderItem, Product

router = APIRouter(prefix="/orders", tags=["pedidos"])


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


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user=Depends(get_current_user)):
    order = Order.objects.filter(pk=order_id, user=user).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    return serialize(order)
