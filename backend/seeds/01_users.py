"""Seed: Create initial admin users (Jose Pedro + Gustavo)"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.service import hash_password
from src.common.database import async_session, engine
from src.common.database import Base
import src.models  # noqa: F401

USERS = [
    {
        "email": "josepedro@goeva.ai",
        "name": "Jose Pedro Gama",
        "password": "admin123",  # Change in production!
        "role": "admin",
    },
    {
        "email": "gustavo@goeva.ai",
        "name": "Gustavo Cermeno",
        "password": "admin123",  # Change in production!
        "role": "admin",
    },
]


async def seed():
    async with async_session() as db:
        for user_data in USERS:
            result = await db.execute(select(User).where(User.email == user_data["email"]))
            if result.scalar_one_or_none():
                print(f"  User {user_data['email']} already exists, skipping")
                continue

            user = User(
                email=user_data["email"],
                name=user_data["name"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
            )
            db.add(user)
            print(f"  Created user: {user_data['name']} ({user_data['email']})")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
