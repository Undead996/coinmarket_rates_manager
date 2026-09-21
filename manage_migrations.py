#!/usr/bin/env python3
"""
Database Migration Management Script
Provides commands for creating and applying database migrations using Alembic
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.database import validate_mysql_config

load_dotenv()

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print(f"✅ {description} завершено успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении: {description}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False

def check_database_connection():
    """Check if database connection is working"""
    try:
        mysql_config = validate_mysql_config()
        print(f"✅ Конфигурация MySQL валидна:")
        print(f"   Host: {mysql_config['MYSQL_HOST']}")
        print(f"   Port: {mysql_config['MYSQL_PORT']}")
        print(f"   User: {mysql_config['MYSQL_USER']}")
        print(f"   Database: {mysql_config['MYSQL_DATABASE']}")
        return True
    except SystemExit:
        print("❌ Ошибка конфигурации базы данных")
        return False

def init_migrations():
    """Initialize Alembic migrations"""
    if not check_database_connection():
        return False
    
    # Check if migrations directory already exists
    if Path("migrations/versions").exists():
        print("ℹ️  Миграции уже инициализированы")
        return True
    
    # Create versions directory
    Path("migrations/versions").mkdir(parents=True, exist_ok=True)
    
    print("✅ Миграции инициализированы")
    return True

def create_migration(message=None):
    """Create a new migration"""
    if not check_database_connection():
        return False
    
    if not init_migrations():
        return False
    
    if not message:
        message = input("Введите описание миграции: ").strip()
        if not message:
            message = "Auto-generated migration"
    
    command = f"alembic revision --autogenerate -m \"{message}\""
    return run_command(command, f"Создание миграции: {message}")

def upgrade_database(revision="head"):
    """Apply migrations to database"""
    if not check_database_connection():
        return False
    
    command = f"alembic upgrade {revision}"
    return run_command(command, f"Применение миграций до {revision}")

def downgrade_database(revision):
    """Downgrade database to specific revision"""
    if not check_database_connection():
        return False
    
    command = f"alembic downgrade {revision}"
    return run_command(command, f"Откат миграций до {revision}")

def show_current_revision():
    """Show current database revision"""
    if not check_database_connection():
        return False
    
    command = "alembic current"
    return run_command(command, "Получение текущей ревизии")

def show_migration_history():
    """Show migration history"""
    if not check_database_connection():
        return False
    
    command = "alembic history"
    return run_command(command, "Получение истории миграций")

def create_initial_migration():
    """Create initial migration for existing models"""
    if not check_database_connection():
        return False
    
    if not init_migrations():
        return False
    
    return create_migration("Initial migration - create all tables")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("""
🗄️  Управление миграциями базы данных

Использование: python manage_migrations.py <команда> [аргументы]

Команды:
  init                    - Инициализировать миграции
  create [описание]       - Создать новую миграцию
  upgrade [ревизия]       - Применить миграции (по умолчанию: head)
  downgrade <ревизия>     - Откатить до указанной ревизии
  current                 - Показать текущую ревизию
  history                 - Показать историю миграций
  initial                 - Создать начальную миграцию для существующих моделей
  check                   - Проверить подключение к базе данных

Примеры:
  python manage_migrations.py init
  python manage_migrations.py create "Add user table"
  python manage_migrations.py upgrade
  python manage_migrations.py downgrade -1
  python manage_migrations.py current
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "init":
        init_migrations()
    elif command == "create":
        message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        create_migration(message)
    elif command == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        upgrade_database(revision)
    elif command == "downgrade":
        if len(sys.argv) < 3:
            print("❌ Укажите ревизию для отката")
            return
        downgrade_database(sys.argv[2])
    elif command == "current":
        show_current_revision()
    elif command == "history":
        show_migration_history()
    elif command == "initial":
        create_initial_migration()
    elif command == "check":
        check_database_connection()
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()
