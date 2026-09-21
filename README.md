# CoinMarket API Backend

Бэкенд проект на FastAPI с CRUD операциями, MySQL базой данных, системой миграций и аутентификацией.

## Возможности

- ✅ Регистрация и аутентификация пользователей
- ✅ JWT токены для авторизации
- ✅ CRUD операции для валют и курсов
- ✅ MySQL база данных
- ✅ Система миграций с Alembic
- ✅ Защищенные эндпоинты
- ✅ Валидация данных с Pydantic
- ✅ Интеграция с CoinMarketCap API

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте переменные окружения в файле `.env`:
```env
SECRET_KEY=your-secret-key-here-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
COINMARKETCAP_HOST=https://pro-api.coinmarketcap.com

# MySQL Database Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=coinmarket_db
```

3. Настройте базу данных:

### Создание базы данных
```bash
# Создать базу данных MySQL (если не существует)
python db_utils.py create-db

# Проверить подключение к базе данных
python db_utils.py test
```

### Инициализация миграций
```bash
# Инициализировать систему миграций
python manage_migrations.py init

# Создать начальную миграцию для существующих моделей
python manage_migrations.py initial

# Применить миграции к базе данных
python manage_migrations.py upgrade
```

4. Запустите сервер:
```bash
python main.py
```

Или с помощью uvicorn:
```bash
uvicorn main:app --reload
```

## Управление миграциями

### Команды для работы с миграциями

```bash
# Проверить статус миграций
python manage_migrations.py current

# Показать историю миграций
python manage_migrations.py history

# Создать новую миграцию (автогенерация на основе изменений в моделях)
python manage_migrations.py create "Описание изменений"

# Применить все миграции
python manage_migrations.py upgrade

# Применить миграции до определенной ревизии
python manage_migrations.py upgrade <revision_id>

# Откатить миграции до предыдущей версии
python manage_migrations.py downgrade -1

# Откатить до определенной ревизии
python manage_migrations.py downgrade <revision_id>

# Проверить подключение к базе данных
python manage_migrations.py check
```

### Структура миграций

Проект использует Alembic для управления миграциями базы данных:

- `migrations/env.py` - конфигурация окружения Alembic
- `migrations/versions/` - директория с файлами миграций
- `001_initial_migration.py` - создание всех таблиц
- `002_add_caching_time_setting.py` - добавление настройки кэширования

### Утилиты для работы с базой данных

```bash
# Показать все таблицы в базе данных
python db_utils.py show-tables

# Создать все таблицы из моделей (без миграций)
python db_utils.py create-tables

# Удалить все таблицы (ОПАСНО!)
python db_utils.py drop-tables

# Удалить всю базу данных (ОПАСНО!)
python db_utils.py drop-db
```

## Создание администратора

После применения миграций необходимо создать пользователя-администратора:

```bash
# Создать пользователя admin с паролем admin
python create_admin_user.py
```

Скрипт создаст пользователя со следующими данными:
- **Логин**: admin
- **Пароль**: admin
- **Статус**: активный

⚠️ **Важно**: Обязательно смените пароль администратора после первого входа в систему!

Скрипт автоматически:
- Проверяет существование пользователя admin
- Хеширует пароль с помощью bcrypt
- Создает запись в таблице users
- Предотвращает создание дубликатов

## API Эндпоинты

### Аутентификация
- `POST /register` - Регистрация нового пользователя
- `POST /token` - Получение JWT токена (логин)
- `GET /users/me` - Получение информации о текущем пользователе

### Пользователи
- `GET /users` - Получение списка всех пользователей (требует авторизации)
- `GET /users/{user_id}` - Получение пользователя по ID (требует авторизации)

### Валюты
- `GET /currencies` - Получение списка всех валют
- `GET /currencies/rates` - Получение валют с последними курсами
- `POST /currencies` - Создание новой валюты (требует авторизации)
- `PATCH /currencies/{currency_id}` - Обновление валюты (требует авторизации)
- `DELETE /currencies/{currency_id}` - Удаление валюты (требует авторизации)

### Курсы валют
- `GET /currencies/{currency_id}/rates` - Получение курсов для валюты
- `POST /currencies/{currency_id}/rates` - Создание нового курса (требует авторизации)
- `PATCH /currencies/{currency_id}/rates/{rate_id}` - Обновление курса (требует авторизации)
- `DELETE /currencies/{currency_id}/rates/{rate_id}` - Удаление курса (требует авторизации)

### Настройки
- `GET /settings` - Получение всех настроек
- `GET /settings/active` - Получение активных настроек
- `GET /settings/{setting_id}` - Получение настройки по ID
- `GET /settings/name/{setting_name}` - Получение настройки по имени
- `POST /settings` - Создание настройки (требует авторизации)
- `PUT /settings/{setting_id}` - Обновление настройки (требует авторизации)
- `DELETE /settings/{setting_id}` - Удаление настройки (требует авторизации)

### CoinMarketCap
- `GET /v1/cryptocurrency/quotes/latest` - Прокси для CoinMarketCap API

## Документация API

После запуска сервера доступна интерактивная документация:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Структура проекта

```
coinmarket/
├── src/
│   ├── auth/           # Аутентификация и авторизация
│   ├── cache/          # Кэширование
│   ├── calculate/      # Расчеты курсов валют
│   ├── db/             # Конфигурация базы данных
│   ├── models/         # SQLAlchemy модели
│   └── schemas/        # Pydantic схемы
├── controllers/        # Контроллеры CRUD операций
├── routers/           # FastAPI роутеры
├── migrations/        # Alembic миграции
├── static/           # Статические файлы
├── manage_migrations.py  # Управление миграциями
├── db_utils.py       # Утилиты для работы с БД
├── migrate_to_mysql.py  # Миграция с SQLite на MySQL
└── main.py           # Точка входа приложения
```
