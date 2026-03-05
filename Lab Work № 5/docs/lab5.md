# Лабораторная работа №5 — Docker (микросервисная архитектура) + CI + интеграционные тесты

## 1. Цель работы
Получить опыт организации взаимодействия сервисов с использованием Docker-контейнеров.

## 2. Архитектура (контейнеры)
Минимум 3 контейнера:
- **client**: Nginx + статическая HTML/JS-страница
- **server**: FastAPI (Python)
- **db**: PostgreSQL

PlantUML диаграмма: `PlantUML/c4_containers_lab5.puml`

## 3. Реализация контейнеров
### 3.1. Server (FastAPI + PostgreSQL)
- Код: `server/app/main.py`
- Подключение к БД: переменная окружения `DATABASE_URL`
- При старте создаются таблицы и сидируются балансы поинтов: `u1=5000`, `u2=2000` (как в ЛР4).

### 3.2. Client (Nginx)
- Код: `client/index.html`, `client/app.js`
- Nginx проксирует `/api/*` на контейнер `server`, поэтому CORS не требуется.

### 3.3. Docker Compose
- Файл: `docker-compose.yml`
- Порты:
  - client: http://localhost:8080
  - server: http://localhost:8000
  - db: localhost:5432

## 4. Как запустить локально
Из папки **Lab Work № 5**:

```bash
docker compose up --build
```

Проверка:
- открыть `http://localhost:8080`
- нажать **Создать демо-товар**
- нажать **Загрузить товары**

## 5. Интеграционные тесты (Postman/Newman)
Используются тесты из ЛР4:
- `tests/postman/Lab4_Merch_autotests.postman_collection.json`
- `tests/postman/Lab4_Local_autotests.postman_environment.json` (baseUrl = http://127.0.0.1:8000)

Локальный запуск newman (если установлен Node.js):

```bash
npm i -g newman
newman run tests/postman/Lab4_Merch_autotests.postman_collection.json \
  -e tests/postman/Lab4_Local_autotests.postman_environment.json
```

## 6. CI (GitHub Actions)
Workflow добавляется в `.github/workflows/ci.yml` на уровне репозитория:
- собирает docker-образы
- поднимает `docker compose up -d`
- ждёт `GET /health`
- запускает newman-тесты
