from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.schemas import RegisterIn, TokenOut, UserOut
from api.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn):
    User = get_user_model()
    if User.objects.filter(username=data.username).exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Usuário já existe")
    try:
        validate_password(data.password)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, list(exc.messages))
    return User.objects.create_user(
        username=data.username, email=data.email, password=data.password
    )


@router.post("/token", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    # Usa o sistema de autenticação do Django (mesmos usuários do admin)
    user = authenticate(username=form.username, password=form.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha incorretos")
    return TokenOut(access_token=create_access_token(user.pk))


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user
