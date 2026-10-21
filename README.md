# Loja — Django + FastAPI + MySQL

Um único projeto, um único servidor ASGI:

| Rota        | Quem atende | Para quê                                  |
|-------------|-------------|-------------------------------------------|
| `/admin/`   | Django      | Painel: categorias, produtos, pedidos     |
| `/api/*`    | FastAPI     | API REST (docs em `/api/docs`)            |

O FastAPI reutiliza os **models, o ORM e os usuários do Django**
(`config/asgi.py` faz o roteamento entre os dois).

## Rodando

```bash
# 1. ambiente
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

# 2. configuração
copy .env.example .env          # Linux/Mac: cp .env.example .env

# 3. MySQL via Docker
docker compose up -d

# 4. banco + usuário admin
python manage.py migrate
python manage.py createsuperuser

# 5. servidor
uvicorn config.asgi:application --reload
```

- Admin: http://localhost:8000/admin/
- Docs da API: http://localhost:8000/api/docs

> Sem Docker/MySQL por enquanto? Coloque `DB_ENGINE=sqlite` no `.env`.

## Endpoints

| Método | Rota                    | Acesso   |
|--------|-------------------------|----------|
| POST   | `/api/auth/register`    | público  |
| POST   | `/api/auth/token`       | público (retorna JWT) |
| GET    | `/api/auth/me`          | logado   |
| GET    | `/api/categories`       | público  |
| POST   | `/api/categories`       | admin    |
| GET    | `/api/products`         | público (`?q=`, `?category=`, `limit`, `offset`) |
| GET    | `/api/products/{slug}`  | público  |
| POST   | `/api/products`         | admin    |
| PATCH  | `/api/products/{id}`    | admin    |
| POST   | `/api/orders`           | logado (baixa estoque com lock) |
| GET    | `/api/orders`           | logado (só os seus) |
| GET    | `/api/orders/{id}`      | logado (só os seus) |

## Estrutura

```
config/   settings, urls, asgi.py (despacha Django x FastAPI)
shop/     app Django: models, admin, migrations
api/      app FastAPI: main, schemas, security (JWT), routers/
```

## Notas

- `mysqlclient` no Windows usa wheel pronta; no Linux precisa de
  `libmysqlclient-dev` e `pkg-config` antes do `pip install`.
- Em produção: `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` forte,
  `python manage.py collectstatic` e `DJANGO_ALLOWED_HOSTS` com seu domínio.
- Endpoints FastAPI são `def` (síncronos) de propósito: rodam em threadpool,
  onde o ORM do Django é seguro. Evite ORM dentro de `async def` sem `sync_to_async`.
