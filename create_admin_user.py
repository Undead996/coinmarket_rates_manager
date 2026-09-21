#!/usr/bin/env python3
"""
Script to create admin user
Creates a user with login=admin and password=admin
"""

import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.database import SessionLocal
from src.schemas.schemas import UserCreate
from controllers.crud_controller import create_user, get_user_by_username

def create_admin_user():
    """Create admin user if it doesn't exist"""
    db = SessionLocal()
    try:
        # Check if admin user already exists
        existing_user = get_user_by_username(db, "admin")
        if existing_user:
            print("❌ Пользователь 'admin' уже существует")
            return False
        
        # Create admin user
        user_data = UserCreate(
            username="admin",
            password="admin"
        )
        
        admin_user = create_user(db=db, user=user_data)
        
        if admin_user:
            print("✅ Пользователь 'admin' успешно создан")
            print(f"   ID: {admin_user.id}")
            print(f"   Username: {admin_user.username}")
            print(f"   Active: {admin_user.is_active}")
            print(f"   Created: {admin_user.created_at}")
            return True
        else:
            print("❌ Ошибка при создании пользователя")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🔄 Создание администратора...")
    success = create_admin_user()
    
    if success:
        print("\n✅ Администратор создан успешно!")
        print("Данные для входа:")
        print("  Логин: admin")
        print("  Пароль: admin")
    else:
        print("\n❌ Не удалось создать администратора")
        sys.exit(1)
