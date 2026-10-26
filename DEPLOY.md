# Инструкция по развертыванию проекта Taskmanager (Backend + Frontend + PostgreSQL)

Данное руководство содержит пошаговую инструкцию по подготовке сервера и промышленному развертыванию (деплою) системы управления задачами с использованием Docker и Docker Compose.

---

## 🏛 Архитектура развертывания

Система состоит из трех изолированных сервисов, объединенных внутренней виртуальной сетью Docker:

```
[ Пользователь / Браузер ]
            │
     HTTP/HTTPS (:80 / :443)
            │
            ▼
┌────────────────────────────────────────────────────────┐
│  webui (Nginx + React SPA)                             │
│  - Отдает скомпилированную статику React               │
│  - Роутинг SPA (HTML5 History API)                     │
│  - Проксирует /api/ -> http://taskservice:8000         │
│  - Проксирует /docs -> http://taskservice:8000         │
│  - Gzip-сжатие, заголовки безопасности, кэш ассетов    │
└──────────────────────────┬─────────────────────────────┘
                           │ internal network
                           ▼
┌────────────────────────────────────────────────────────┐
│  taskservice (FastAPI + Python 3.13)                   │
│  - REST API микросервис на базе Uvicorn                │
│  - Запуск от непривилегированного пользователя appuser │
│  - Встроенный healthcheck (/api/health)                │
│  - Логирование с ротацией в named volume               │
└──────────────────────────┬─────────────────────────────┘
                           │ internal network (:5432)
                           ▼
┌────────────────────────────────────────────────────────┐
│  db (PostgreSQL 17 Alpine)                             │
│  - Хранение данных в постоянном томе (named volume)    │
│  - Изоляция от внешней сети (порт закрыт снаружи)      │
│  - Встроенная проверка готовности (pg_isready)         │
└────────────────────────────────────────────────────────┘
```

**Преимущества архитектуры:**
- **Отсутствие проблем с CORS:** фронтенд и API находятся на одном источнике (origin).
- **Безопасные сессии:** аутентификационные `HttpOnly` cookie передаются прозрачно браузером без междоменных ограничений (SameSite: Lax).
- **Безопасность сетевого контура:** порты базы данных и внутреннего API не торчат наружу в открытый интернет.

---

## 📋 Минимальные системные требования

- **ОС:** Ubuntu 22.04 / 24.04 LTS, Debian 12, Rocky Linux 9 или любая Linux-система с ядром 5.x+
- **CPU:** от 1 vCPU (рекомендуется 2 vCPU)
- **RAM:** от 1.5 GB (рекомендуется 2 GB+)
- **Диск:** от 10 GB свободного пространства (SSD/NVMe)
- **Сетевой доступ:** открытые порты `80` (HTTP), `443` (HTTPS) и `22` (SSH)

---

## 🚀 Шаг 1. Подготовка сервера

### 1.1. Обновление пакетов
Подключитесь к серверу по SSH и обновите репозитории:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git ufw
```

### 1.2. Установка Docker и Docker Compose
Установите официальный Docker Engine с плагином Compose:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

> **Важно:** после добавления пользователя в группу `docker`, перелогиньтесь в SSH или выполните `newgrp docker`.

Проверьте корректность установки:
```bash
docker --version
docker compose version
```

### 1.3. Настройка базового файрвола (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 80/tcp comment "HTTP"
sudo ufw allow 443/tcp comment "HTTPS"
sudo ufw enable
```

---

## 📦 Шаг 2. Размещение проекта и настройка `.env`

### 2.1. Клонирование репозитория
Склонируйте проект в рабочую директорию (например, `/opt/taskmanager` или домашний каталог):

```bash
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> /opt/taskmanager
cd /opt/taskmanager
```

### 2.2. Создание файла конфигурации `.env`
Создайте боевой файл `.env` из примера:

```bash
cp .env.example .env
```

Сгенерируйте надежный криптографический ключ для JWT-токенов:
```bash
openssl rand -hex 32
```

Отредактируйте `.env`:
```bash
nano .env
```

**Пример боевого `.env` файла:**
```env
# Порт для входящих HTTP-запросов (Nginx)
FRONTEND_PORT=80

# Порты для локальной отладки (слушают только локалхост сервера)
API_PORT=127.0.0.1:8000
DB_PORT=127.0.0.1:5432

# Настройки PostgreSQL
POSTGRES_USER=taskmanager_admin
POSTGRES_PASSWORD=SuperStrongDbPassword_982!
POSTGRES_DB=taskmanager

# Секретный ключ подписи сессий (вставьте сгенерированный openssl rand -hex 32)
APP_SECRET_KEY=9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b

# Время жизни токенов
APP_ACCESS_TOKEN_EXPIRE_MINUTES=1440
APP_INVITE_TOKEN_EXPIRE_HOURS=48

# Безопасность Cookie:
# Если проект работает за HTTPS/SSL — установите true!
# Если проект разворачивается без домена напрямую по HTTP IP-адресу — оставьте false.
APP_AUTH_COOKIE_SECURE=false

# Режим отладки (в продакшене строго false)
APP_DEBUG=false
APP_LOG_LEVEL=INFO
```

---

## 🛠 Шаг 3. Сборка и запуск контейнеров

Запустите сборку образов и старт всех сервисов в фоновом режиме:

```bash
docker compose up -d --build
```

### Проверка статуса:
```bash
docker compose ps
```

Вы должны увидеть три работающих контейнера со статусом `healthy`:
```
NAME                  IMAGE                  COMMAND                  SERVICE       CREATED         STATUS                   PORTS
taskmanager-db        postgres:17-alpine     "docker-entrypoint.s…"   db            1 minute ago    Up 1 minute (healthy)    127.0.0.1:5432->5432/tcp
taskmanager-backend   project-taskservice    "python -m uvicorn t…"   taskservice   1 minute ago    Up 1 minute (healthy)    127.0.0.1:8000->8000/tcp
taskmanager-webui     project-webui          "nginx -g 'daemon of…"   webui         1 minute ago    Up 1 minute (healthy)    0.0.0.0:80->80/tcp
```

### Просмотр логов:
```bash
# Все логи в реальном времени:
docker compose logs -f

# Логи только бэкенда:
docker compose logs -f taskservice

# Логи веб-сервера / Nginx:
docker compose logs -f webui
```

---

## 👤 Шаг 4. Инициализация базы данных и создание администратора

### 4.1. Применение миграций базы данных (Alembic)
Хотя приложение при старте автоматически валидирует базовую схему, зафиксируйте актуальное состояние миграций Alembic:

```bash
docker compose exec taskservice alembic upgrade head
```

### 4.2. Создание учетной записи администратора
Для первого входа в систему создайте учетную запись администратора с помощью встроенной CLI-утилиты `taskmanager-cli`:

```bash
docker compose exec taskservice taskmanager-cli create-admin \
  --username admin \
  --password "YourSecureAdminPassword123!" \
  --email "admin@yourcompany.com"
```

При успешном выполнении вы увидите:
`[OK] Администратор 'admin' (ID: 1) успешно создан.`

### 4.3. Генерация инвайт-токенов для регистрации коллег
Регистрация новых пользователей в системе защищена и доступна только по одноразовым приглашениям:

```bash
docker compose exec taskservice taskmanager-cli create-invite --admin admin --hours 48
```

Команда сгенерирует токен, который пользователь указывает в форме регистрации в WebUI.

### 4.4. Проверка списка пользователей
```bash
docker compose exec taskservice taskmanager-cli list-users
```

---

## 🔒 Шаг 5. Настройка HTTPS / Домена (Production)

Для промышленного использования настоятельно рекомендуется подключить домен и настроить SSL/TLS сертификат (Let's Encrypt).

### Вариант: Использование Nginx на хосте с Certbot

Если на сервере развернут хостовый Nginx:

1. Установите Certbot:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   ```

2. В `.env` проекта измените порт фронтенда, чтобы освободить порт 80 для хостового Nginx:
   ```env
   FRONTEND_PORT=127.0.0.1:3000
   APP_AUTH_COOKIE_SECURE=true
   ```
   Перезапустите контейнеры:
   ```bash
   docker compose up -d
   ```

3. Создайте конфигурацию хостового Nginx `/etc/nginx/sites-available/tasks.conf`:
   ```nginx
   server {
       server_name tasks.yourdomain.com;

       client_max_body_size 30M;

       location / {
           proxy_pass http://127.0.0.1:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto https;
       }
   }
   ```

4. Активируйте сайт и выпустите SSL-сертификат:
   ```bash
   sudo ln -s /etc/nginx/sites-available/tasks.conf /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   sudo certbot --nginx -d tasks.yourdomain.com
   ```

---

## 💾 Шаг 6. Резервное копирование и восстановление (Backups)

### 6.1. Резервная копия базы данных
Для создания горячего дампа PostgreSQL выполните:

```bash
docker compose exec -T db pg_dump -U taskmanager taskmanager | gzip > /opt/backups/taskmanager_$(date +%Y%m%d_%H%M%S).sql.gz
```

### 6.2. Автоматизация бэкапов через cron
Добавьте задачу в `crontab -e`:

```cron
# Ежедневный бэкап в 03:00 ночи с хранением последних 14 дней
0 3 * * * mkdir -p /opt/backups && docker compose -f /opt/taskmanager/docker-compose.yml exec -T db pg_dump -U taskmanager taskmanager | gzip > /opt/backups/taskmanager_$(date +\%Y\%m\%d).sql.gz && find /opt/backups -name "taskmanager_*.sql.gz" -mtime +14 -delete
```

### 6.3. Восстановление из бэкапа
```bash
gunzip -c /opt/backups/taskmanager_20261026.sql.gz | docker compose exec -T db psql -U taskmanager taskmanager
```

---

## 🔄 Шаг 7. Обновление проекта (CI/CD / Manual Update)

Когда в git-репозитории появляются новые коммиты:

```bash
cd /opt/taskmanager

# 1. Получаем свежий код
git pull origin main

# 2. Пересобираем и обновляем контейнеры без остановки базы
docker compose build
docker compose up -d

# 3. Применяем свежие миграции если были изменения в схеме БД
docker compose exec taskservice alembic upgrade head

# 4. Очищаем старые неиспользуемые Docker-образы
docker image prune -f
```

---

## 🧰 Шпаргалка по полезным командам

| Команда | Описание |
|---|---|
| `docker compose ps` | Статус всех сервисов и их healthcheck |
| `docker compose logs -f` | Просмотр всех логов в реальном времени |
| `docker compose logs -f taskservice` | Логи бэкенда |
| `docker compose restart taskservice` | Перезапуск только бэкенда |
| `docker compose down` | Остановка всех контейнеров с сохранением данных |
| `docker compose down -v` | ⚠️ **Внимание:** удаление контейнеров вместе с томами данных БД |
| `docker compose exec taskservice bash` | Вход в командную оболочку контейнера бэкенда |
| `docker compose exec db psql -U taskmanager` | Интерактивная консоль PostgreSQL |
