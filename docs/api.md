# API и Swagger

После запуска `docker compose up --build -d`:

- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- Живая OpenAPI 3.1: http://localhost:8080/openapi.json
- Зафиксированный контракт: [openapi.json](openapi.json)
- Коллекция: [postman_collection.json](postman_collection.json)

Base URL API: `http://localhost:8080`. Frontend использует `http://localhost:5173/api` через nginx. Swagger открывайте напрямую на 8080: backend генерирует ссылки без префикса `/api`. Ресурсы Swagger/ReDoc по умолчанию берутся с CDN; для полностью изолированной сети их нужно поставить локально.

## Как отправить запрос в Swagger

1. Откройте `POST /auth/login`, нажмите **Try it out**, введите `{"email":"demo@alfa.ru","password":"demo123"}` и нажмите **Execute**.
2. Скопируйте только `access_token` из ответа.
3. Нажмите **Authorize** и вставьте токен без слова `Bearer` (используется HTTP Bearer).
4. Выполните `GET /auth/me`, `GET /applications` и откройте заявку по её ID.

JWT передаётся как `Authorization: Bearer <token>`. Клиент ограничен своей компанией, банковские операции требуют роли. `demo` разрешает обе зоны для показа. Пароль и токен нельзя добавлять в URL или публичные логи.

## Документы

Реальная загрузка — `POST /applications/{app_id}/documents/file` (`multipart/form-data`, поля описаны в Swagger). Файлы PDF/JPEG/PNG до 5 МБ сохраняются в томе `uploads`; скачивание — `GET /applications/{app_id}/documents/{doc_type}/file`. JSON-метаданные через `/documents` сохранены для синтетического API-сценария. Метаданные сами по себе не содержат файл; несуществующее содержимое скачать нельзя.

## Коллекция и проверка контракта

Импортируйте коллекцию в Postman, запускайте запросы по порядку. `base_url` задаётся переменной коллекции; JWT, ID продукта, заявки и кредита сопровождения выбираются автоматически. Создаётся синтетическая заявка и три записи метаданных документов. Политика не активируется, деньги не переводятся, действия сопровождения не применяются.

Можно выполнить тот же JSON без Postman: `python3 scripts/run_collection.py`. Скрипт делает запросы из коллекции и проверяет HTTP-статусы; он не исполняет произвольный JavaScript Postman. Генерация snapshot: `python3 scripts/export_openapi.py`; сравнение с живым API: `python3 scripts/check_contract.py --live`.

## Эндпоинты текущей сборки

| Метод | Путь | Операция |
|---|---|---|
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Me |
| POST | `/auth/register` | Register |
| GET | `/auth/company` | Company |
| GET | `/products` | List Products |
| GET | `/applications` | List Applications |
| POST | `/applications` | Create Application |
| PATCH | `/applications/{app_id}` | Update Application |
| GET | `/applications/{app_id}` | Get Application |
| GET | `/applications/{app_id}/documents` | List Documents |
| POST | `/applications/{app_id}/documents` | Upload Document |
| DELETE | `/applications/{app_id}/documents/{doc_type}` | Delete Document |
| GET | `/applications/{app_id}/readiness` | Readiness |
| GET | `/applications/{app_id}/enrichment` | Get Enrichment |
| GET | `/applications/{app_id}/score` | Get Score |
| POST | `/applications/{app_id}/submit` | Submit Application |
| GET | `/applications/{app_id}/copilot` | Application Copilot |
| GET | `/applications/{app_id}/offers` | Personalized Offers |
| GET | `/applications/{app_id}/servicing` | Get Servicing |
| POST | `/applications/{app_id}/servicing/autopilot` | Configure Autopilot |
| POST | `/applications/{app_id}/servicing/autopilot/run` | Run Autopilot |
| POST | `/applications/{app_id}/servicing/forecast` | Servicing Forecast |
| POST | `/applications/{app_id}/servicing/apply` | Apply Servicing |
| POST | `/applications/{app_id}/simulate` | Simulate Conditions |
| POST | `/applications/{app_id}/review` | Request Review |
| POST | `/applications/{app_id}/resubmit` | Resubmit Application |
| POST | `/applications/{app_id}/accept` | Accept Offer |
| POST | `/applications/{app_id}/transition` | Transition Application |
| POST | `/applications/{app_id}/conditions` | Save Conditions |
| GET | `/applications/{app_id}/collaboration` | Get Collaboration |
| POST | `/applications/{app_id}/collaboration` | Update Collaboration |
| POST | `/applications/{app_id}/documents/file` | Upload Document File |
| GET | `/applications/{app_id}/documents/{doc_type}/file` | Download Document File |
| POST | `/calc` | Calc |
| POST | `/recommend` | Recommend |
| GET | `/policies` | List Policies |
| POST | `/policies` | Create Policy |
| GET | `/policies/active` | Active Policy |
| GET | `/policies/audit` | Policy Audit |
| POST | `/policies/simulate` | Simulate Policy |
| POST | `/policies/{version}/activate` | Activate Policy |
| GET | `/portfolio/early-warnings` | Early Warnings |
| GET | `/portfolio/metrics` | Metrics |
| GET | `/health` | Health |

## Границы прототипа

Скоринг — ручная scorecard, вероятность в конструкторе — учебный индикатор; кредитная политика — правила YAML. LLM отключена по умолчанию и отвечает только за текст копилота при включении. Внешние источники, ПЭП и выдача синтетические. Для промышленной версии нужны idempotency keys, outbox, наблюдаемость и меры из [SECURITY.md](../credit-conveyor/docs/SECURITY.md).
