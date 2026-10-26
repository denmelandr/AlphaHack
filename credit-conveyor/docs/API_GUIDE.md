# API guide

Полная машиночитаемая спецификация находится в [`openapi.json`](openapi.json), а интерактивная
Swagger-документация доступна после запуска по адресу `http://localhost:8080/docs`.

Base URL для локального запуска: `http://localhost:8080`.

## Аутентификация

1. Выполнить `POST /auth/login` с email и паролем.
2. Взять `access_token` из ответа.
3. Передавать его как `Authorization: Bearer <token>`.

Доступ к объектам ограничен ролью и компанией пользователя. Банковские роли видят
портфель, а клиент видит заявки своей компании. Демо-роль объединяет оба представления
для демонстрации.

## Сценарий клиента

| Шаг | Метод | Endpoint | Назначение |
|---:|---|---|---|
| 1 | POST | `/auth/login` | получить JWT |
| 2 | GET | `/products` | посмотреть кредитные продукты |
| 3 | POST | `/recommend` | подобрать продукт по JTBD-ответам |
| 4 | POST | `/calc` | рассчитать платёж и переплату |
| 5 | POST | `/applications` | создать заявку |
| 6 | POST | `/applications/{id}/documents` | добавить метаданные документа |
| 7 | GET | `/applications/{id}/readiness` | проверить готовность |
| 8 | POST | `/applications/{id}/submit` | отправить заявку в конвейер |
| 9 | GET | `/applications/{id}` | получить обогащение, scorecard, решение и оффер |
| 10 | POST | `/applications/{id}/simulate` | проверить альтернативные сумму/срок/залог |
| 11 | POST | `/applications/{id}/review` | запросить ручной пересмотр |
| 12 | POST | `/applications/{id}/accept` | принять оффер; выдача моделируется |

## Сопровождение кредита

| Метод | Endpoint | Назначение |
|---|---|---|
| GET | `/applications/{id}/servicing` | счёт, сигналы, радар и действия |
| POST | `/applications/{id}/servicing/forecast` | what-if: падение выручки/разовый расход |
| POST | `/applications/{id}/servicing/apply` | применить действие сопровождения |
| POST | `/applications/{id}/servicing/autopilot` | задать правила автопилота |
| POST | `/applications/{id}/servicing/autopilot/run` | выполнить разрешённое действие |
| GET | `/applications/{id}/offers` | персональные предложения по профилю |

Пример what-if:

```json
{
  "revenue_drop_pct": 45,
  "extra_expense": 0
}
```

Пример настройки автопилота:

```json
{
  "enabled": true,
  "max_bridge": 100000
}
```

Автопилот не создаёт новый долг выше установленного лимита. Все применённые действия
попадают в журнал кредитного счёта.

## Сценарий банка

| Метод | Endpoint | Назначение |
|---|---|---|
| GET | `/applications` | очередь заявок |
| GET | `/applications/{id}/copilot` | саммари и аномалии |
| POST | `/applications/{id}/transition` | ручной переход по state machine |
| GET | `/policies` | версии политик |
| GET | `/policies/active` | активная политика |
| POST | `/policies/simulate` | shadow/challenger-симуляция |
| POST | `/policies/{version}/activate` | активация версии |
| GET | `/policies/audit` | аудит policy-изменений |
| GET | `/portfolio/early-warnings` | очередь ранних предупреждений |
| GET | `/portfolio/metrics` | портфельные метрики эффекта |

## Идемпотентность и ограничения прототипа

В production для командных операций должны использоваться idempotency key и correlation
ID на уровне gateway/outbox. В текущем MVP состояние и аудит сохраняются транзакционно в
PostgreSQL, а внешние источники заменены локальными моками. Это явно указано в
`THIRD_PARTY_NOTICES.md` и `docs/SECURITY.md`.
