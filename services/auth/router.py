from fastapi import APIRouter, Depends, HTTPException, status

from database import Database, get_database
from models import UserRecord
from services.auth.dependencies import get_current_user
from services.auth.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    ProviderMismatchError,
    UserValidationError,
)
from services.auth.jwt import access_token_expires_in_seconds, create_access_token
from services.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from services.auth.users import authenticate_user, create_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: RegisterRequest,
    db: Database = Depends(get_database),
) -> UserResponse:
    try:
        user = create_user(
            name=request.name,
            email=str(request.email),
            password=request.password,
            provider="local",
            db=db,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UserValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        provider=user.provider,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    request: LoginRequest,
    db: Database = Depends(get_database),
) -> TokenResponse:
    try:
        user = authenticate_user(
            email=str(request.email),
            password=request.password,
            db=db,
        )
    except ProviderMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=access_token_expires_in_seconds(),
    )


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: UserRecord = Depends(get_current_user),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        provider=current_user.provider,
        picture_url=current_user.picture_url,
        created_at=current_user.created_at,
    )
