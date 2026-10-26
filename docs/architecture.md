# Архитектура решения

## Обзор

Цифровой кредитный конвейер для малого и микробизнеса. Один продукт обслуживает
две стороны — клиента и банк — поверх общего движка принятия решения и единой
машины состояний заявки.

```mermaid
flowchart LR
  subgraph Клиент
    UIc[Веб-кабинет клиента]
  end
  subgraph Банк
    UIb[Консоль банка]
  end
  UIc -->|REST| API
  UIb -->|REST| API
  subgraph Backend["Backend (FastAPI)"]
    API[REST API] --> SM[Машина состояний]
    API --> PIPE[Пайплайн]
    PIPE --> SCORE[Скоринг]
    PIPE --> POLICY[Policy-engine]
    PIPE --> ENR[Обогащение]
    API --> COP[Копилот]
    API --> SRV[Сопровождение]
  end
  ENR -->|REST| MOCK[Моки БКИ/ЕГРЮЛ/ФНС/ОФД]
  COP -.->|опционально| LLM[(Ollama / open-weights)]
  API --> PG[(PostgreSQL)]
  API --> RD[(Redis)]
```

## Компоненты

- **frontend** — React + TypeScript + Vite, две ролевые зоны (клиент, банк).
- **backend** — FastAPI: REST API, машина состояний, пайплайн, скоринг,
  policy-engine, копилот, сопровождение.
- **integrations-mock** — симуляторы внешних источников (БКИ, ЕГРЮЛ/ЕГРИП,
  ФНС «Прозрачный бизнес», ОФД) с упрощёнными контрактами.
- **postgres** — основное хранилище. **redis** — подготовленный инфраструктурный сервис; отдельный worker в этой сборке не запускается.
- **ollama** (опционально) — LLM с открытыми весами для копилота.

## Сквозной пайплайн

```
потребность → продукт → заявка → проверки → обогащение → скоринг → политика
   → (одобрение / контрусловия / запрос данных / отказ) → подписание → выдача → сопровождение
```

Скоринг и решение разделены: скоринг даёт балл риска с факторами, policy-engine
превращает балл вместе с правилами банка в решение и условия.

## Машина состояний заявки

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> SUBMITTED: submit
  SUBMITTED --> VALIDATION: start_validation
  VALIDATION --> ENRICHMENT: validation_ok
  VALIDATION --> NEEDS_INFO: validation_incomplete
  ENRICHMENT --> SCORING: enrichment_done
  SCORING --> DECISIONING: scoring_done
  DECISIONING --> OFFER: decide_approve / decide_counter
  DECISIONING --> NEEDS_INFO: decide_need_info
  DECISIONING --> DECLINED: decide_decline
  DECISIONING --> MANUAL_REVIEW: to_manual_review
  NEEDS_INFO --> VALIDATION: client_resubmit
  NEEDS_INFO --> MANUAL_REVIEW: to_manual_review
  OFFER --> OFFER_ACCEPTED: accept_offer
  OFFER --> DECISIONING: adjust_offer
  OFFER --> MANUAL_REVIEW: to_manual_review
  DECLINED --> MANUAL_REVIEW: to_manual_review
  MANUAL_REVIEW --> OFFER: manual_approve
  MANUAL_REVIEW --> DECLINED: manual_decline
  MANUAL_REVIEW --> NEEDS_INFO: manual_need_info
  OFFER_ACCEPTED --> SIGNING: start_signing
  SIGNING --> DISBURSED: disburse
  DISBURSED --> SERVICING: start_servicing
  DECLINED --> [*]
  SERVICING --> [*]
```

Автоматические переходы (валидация, обогащение, скоринг, решение) выполняет
пайплайн; ручные — клиент (отправка, приём оффера, переотправка) и банк
(подписание, выдача, ручной разбор).

## Модель данных (ERD)

```mermaid
erDiagram
  COMPANY ||--o{ USER : "сотрудники"
  COMPANY ||--o{ APPLICATION : "заявки"
  USER ||--o{ APPLICATION : "подаёт"
  PRODUCT ||--o{ APPLICATION : "продукт"
  APPLICATION ||--o{ APPLICATION_EVENT : "аудит"
  APPLICATION ||--o{ ENRICHMENT_SNAPSHOT : "обогащение"
  APPLICATION ||--o{ SCORE_RESULT : "скоринг"
  APPLICATION ||--o{ DECISION : "решения"
  APPLICATION ||--o{ OFFER : "офферы"
  APPLICATION ||--o{ DOCUMENT : "документы"
  APPLICATION ||--o{ CREDIT_ACCOUNT : "кредит"
  POLICY_VERSION ||--o{ POLICY_AUDIT : "аудит политики"
```

## Enterprise-аспекты

- **Безопасность:** JWT + RBAC (клиентские и банковские роли), аудит переходов
  и изменений политики, секреты в переменных окружения.
- **Надёжность:** healthcheck у сервисов, устойчивые вызовы моков (таймаут,
  ошибка источника не роняет пайплайн), деградация копилота в шаблоны без LLM.
- **Воспроизводимость:** Docker Compose, зафиксированные версии зависимостей,
  синтетический сид, миграции Alembic.
- **Масштабирование:** сервисы stateless, состояние в Postgres/Redis; путь роста —
  вынести скоринг/копилот/интеграции в отдельные сервисы, очередь на Kafka, k8s.

## Enterprise-слой и сопровождение

### Раннее предупреждение

После `DISBURSED → SERVICING` backend создаёт `CreditAccount`. Сервис сопровождения
строит дневной прогноз на 60 дней по выручке, обязательным расходам, налогам,
зарплате, платежу по кредиту и подтверждаемой дебиторке. При отрицательном остатке
радар фиксирует дату и размер разрыва, а затем сравнивает варианты помощи через тот же
forecast-движок.

### Дебиторка и цепочная зараза

Контрагенты проверяются локальным `integrations-mock`. Ликвидация и блокировка счёта
помечают дебиторку рискованной; такая сумма исключается из надёжного прогноза. Это
предотвращает выдачу нового долга на основании денег, которые бизнес, вероятно, не
получит.

### Автопилот

Автопилот хранит настройки и журнал в `CreditAccount.autopilot`. Бесплатные и заранее
разрешённые действия могут применяться автоматически. Предодобренный мост ограничен
`max_bridge`; превышение лимита не выполняется автоматически и требует решения человека.

### Банковский портфель

`/portfolio/early-warnings` собирает кредиты с прогнозируемым разрывом или нарушением
ковенантов. `/portfolio/metrics` показывает размер портфеля, сумму под риском, долю
превентивных действий и модельный эффект на 30+ DPD. Поэтому клиентский сигнал и
портфельная очередь используют одну модель и один источник состояния.

### Границы прототипа

Подписание, выдача, банковские транзакции и обновление внешних источников моделируются.
В промышленной версии к этому слою добавляются scheduler/queue, outbox, circuit
breaker, idempotency keys, correlation IDs и наблюдаемость.


## Реализация и источники истины

- `src/connected/` — рабочие экраны, `src/api/client.ts` — HTTP-транспорт.
- PostgreSQL хранит заявки, решения, версии политик, события, документы и кредитные счета. Файлы лежат в Docker-томе `uploads`.
- `credit-conveyor/backend/app/services/state_machine.py` определяет допустимые переходы; API дополнительно проверяет роль и принадлежность компании.
- `scoring.py` — заданная вручную scorecard; `policy.py` — детерминированные правила YAML. Это не обученная модель риска.
- `copilot.py` — шаблонные тексты и правила выявления аномалий. Qwen через Ollama подключается опционально и кредитных решений не принимает.
- Черновики, what-if, решения и действия сопровождения используют API. Старые локальные движки в `src/lab/` сохранены как прототип и не являются источником рабочих банковских решений.
- Подробный состав сущностей: `backend/app/models/`; текущий контракт: [openapi.json](openapi.json).

### Дополнительные переходы конструктора

```mermaid
stateDiagram-v2
  OFFER --> DECISIONING: revise_conditions / adjust_offer
  DECLINED --> DECISIONING: revise_conditions
  NEEDS_INFO --> DECISIONING: revise_conditions
```

### Совместная работа

Анкета хранит состояние задач, согласования и демо-подписи в `form_data`; сервер проверяет роль участника. Это внутренняя модель согласования, без юридической ПЭП и отправки приглашений.
