from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, UserProfile, UserProfileUpdate
from app.services._common import apply_updates


async def get_profile(user: User) -> UserProfile:
    return UserProfile.model_validate(user)


async def update_profile(db: AsyncSession, user: User, data: UserProfileUpdate) -> UserProfile:
    apply_updates(user, data)
    return UserProfile.model_validate(user)


async def change_password(db: AsyncSession, user: User, data: PasswordChange) -> None:
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password = hash_password(data.new_password)
