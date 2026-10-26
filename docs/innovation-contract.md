> Архив проектирования. Текущая сборка описана в [README](../README.md), [архитектуре](architecture.md) и [OpenAPI](openapi.json); требования и ограничения ниже могут относиться к прежней версии.

> Исторический документ этапа проектирования. После интеграции 26.10.2026 актуальны `README.md`, `docs/integration-matrix.md` и `docs/openapi.json`. Локальные заглушки, упомянутые ниже, заменены рабочим API.

# Расширение контракта: кредитная лаборатория

Реализован React-фронтенд, сервер пока не подключён. Исходный контракт: BACKEND_CODEX_PROMPT.md. Этот документ расширяет его; пути ниже — предлагаемое API, а не существующие эндпоинты.

## Что заменить на сервер

- `src/lab/engine.ts`: evaluate / counterOffers / simulatePolicy / forecast / cashCare — детерминированные учебные функции. Скоринг не обучен, проценты одобрения не являются вероятностью. Portfolio — 500 синтетических компаний, seed 2026, не исторические заявки банка.
- `src/lab/store.ts`: localStorage alfa-lab-v1. В проде заменить на серверные ресурсы и запросы. Состояние оригинальной анкеты находится отдельно в alfa-credit-v1; DEMO-1042 и другие компании не являются заявкой пользователя.
- `src/lab/InnovationHub.tsx`: все действия сохраняются в браузере; запросы пересмотра и ответы связаны между демо-ролями, версия политики используется одним движком в обоих кабинетах.
- Переключатель Клиент / Банк — демонстрация. Нужны аутентификация, tenant isolation и серверные проверки каждой операции. Не доверять выбранной роли в браузере.

## Форматы

Суммы — RUB в рублях, JSON number; расчёт и округление графика — на сервере Decimal. Ставки в процентах годовых; maxDti — доля 0..1. Время ISO8601 UTC. Все результаты включают mode (`demo`/`live`), calculatedAt, dataVersion, policyVersion, modelVersion (null для правил). Доступность продукта — отдельное поле, не выводится из рассчитанной потребности.

Conditions: `{ amount, months, collateral, guarantee }`.
Policy: `{ minScore, maxDti, maxAmount, baseRate, collateralBonus, guaranteeBonus }`.
Factor: `{ id, label, value, points, explanation, source }`.
Decision: `{ id, applicationId, result: 'approved'|'counteroffer'|'declined'|'manual_review', score, probability: number|null, factors: Factor[], checks, rate, monthlyPayment, totalInterest, counterOffers: Conditions[], policyVersion, mode }`.
Не подменять отсутствующую вероятность нормализованным баллом. Для ML учитывать калибровку и версию модели.

## FastAPI API v1

| Метод / путь | Тело и результат |
| --- | --- |
| POST /applications/{id}/decision | Решение по зафиксированной версии заявки; возвращает Decision |
| POST /applications/{id}/what-if | Conditions + applicationVersion + policyVersion; Decision preview без изменения исходной заявки |
| POST /applications/{id}/conditions | Conditions + previewId + expectedVersion; сохраняет выбранные условия после серверной проверки актуальности |
| POST /applications/{id}/reviews | `{comment, decisionId}`; Review со статусом pending, assigned или reviewed |
| GET /bank/reviews | Очередь, фильтры, cursor pagination |
| POST /bank/reviews/{id}/response | `{response, expectedVersion}`; сохраняет ответ сотрудника, клиент видит его через API/SSE |
| GET /bank/applications | Очередь заявок и результат текущего решения; фильтры approved/attention |
| GET /bank/policies | Версии, активный champion и авторы |
| POST /bank/policies/simulations | `{candidate: Policy, championVersion, datasetId}`; асинхронная задача, GET по jobId |
| GET /bank/policies/simulations/{id} | before/after approve-rate, newlyApproved/newlyRejected, размер, seed/dataVersion, hash кандидата, статус |
| POST /bank/policies/activate | simulationId + candidateHash + expectedChampionVersion; новая версия, транзакционный аудит |
| GET /companies/{id}/connectors | bank/accounting/ofd/marketplace; disconnected/pending/connected/error, lastSyncedAt, coverage |
| POST /companies/{id}/connectors/{source}/connect | В demo включает синтетический набор; в live возвращает URL безопасной авторизации, секреты не в браузере |
| DELETE /companies/{id}/connectors/{source} | Отзыв подключения/доступа согласно политике хранения |
| GET /companies/{id}/cashflow?horizon=30 | Массив `{date,incoming,outgoing,balance,event}`, интервалы неопределённости, недостающие источники |
| GET /companies/{id}/live-limit | `{calculatedNeed, approvedLimit: null|number, offerId: null|string, validUntil, missingData, mode}` |
| POST /loans/{id}/care/preview | action: restructure/shift/revenue/idle/refinance + parameters; current/proposed график, проценты, комиссии, последствия, offer availability |
| POST /loans/{id}/care/requests | previewId + expectedLoanVersion; pending_bank, с возможностью последующего явного подтверждения клиентом |
| GET /loans/{id}/care/requests | История превентивных действий и фактический статус |
| GET /applications/{id}/collaboration | Участники, серверные роли, задачи и маршрут согласования |
| PATCH /applications/{id}/tasks/{taskId} | `{complete, expectedVersion}`; права задачи проверяет сервер |
| POST /applications/{id}/invitations | Приглашение только с явным действием пользователя; в прототипе заглушка ничего не отправляет |
| POST /applications/{id}/approvals | version + отдельный реальный процесс ПЭП. Текущая демо-подпись не юридическая |
| POST /bank/applications/{id}/copilot | Job: факты + аномалии + черновик со ссылками на источники, modelVersion, generatedAt, requiresHumanReview=true |
| GET /bank/audit | Неизменяемые серверные события, actor из аутентификации |

## Параметры сопровождения

- restructure: `{extension: 6|12|18|24}` месяцев;
- shift: `{dayOfMonth: 5|10|15|20|25}`;
- revenue: `{revenuePercent: number}`; backend возвращает правила минимального платежа, комиссии, срока и условия нулевой выручки;
- idle: `{idleBalance, assumedYield}` — предварительная модель. Реальный продукт и автоматическое погашение подключаются отдельным согласованным процессом;
- refinance: `{assumedRate}` — расчёт; реальные доступные предложения банк возвращает отдельно.

В нынешнем интерфейсе запрос сохраняет действие и параметры. Реальный график не изменяется. Серверная preview должна учитывать проценты до даты изменения, комиссию, округление, актуальный остаток, календарь и наличие оферты.

## Ошибки и проверки

401/403 права, 404 ресурс, 409 конфликт версии или устаревшая симуляция, 422 валидация, 503 внешний сервис недоступен. Envelope `{code,message,fieldErrors,requestId}`. Idempotency-Key для запросов пересмотра, сохранения условий, активации политики и действий по кредиту. Повтор должен возвращать прежний результат.

Тяжёлые расчёты — фоновые задачи со status queued/running/succeeded/failed. Дебаунс what-if и отмена устаревших ответов; для активации использовать только серверный результат симуляции точного hash кандидата на актуальной champion. Подключение коннектора может дать неполные данные — UI показывает покрытие и свежесть.

Банк определяет окончательное решение; текст копилота — редактируемый черновик. Настоящий LLM пока отсутствует: сейчас фронтенд составляет шаблон из правил. Не выдавать его за ответ модели.

## Демо для приёмки

1. Полярная пекарня: исходные условия не проходят, контрпредложения проходят. Примерить альтернативу, увидеть пересчёт факторов/ставки/нагрузки.
2. Создать пересмотр в клиенте, переключить роль Банк, ответить, вернуться и увидеть ответ.
3. Политика: неверный JSON отклоняется; симуляция 500 заявок; изменение JSON делает старую симуляцию непригодной к активации; активация меняет версию и общий движок.
4. Поток: банк+учёт дают разрыв на 12-й день; ОФД/маркетплейсы меняют поступления; без банка прогноз не строится; без учёта показывается неполнота обязательств.
5. Сопровождение: продление уменьшает платёж и увеличивает проценты; сохраняются параметры локального запроса; настоящий график не меняется.
6. Команда: каждая роль отмечает свою задачу; директор может поставить демо-подпись только при готовности всех трёх задач.
7. Копилот: сводка относится к выбранной компании, редактируется, выгружается TXT; маркировка отсутствия LLM видна.

Метрики выдачи/просрочки/реального одобрения заполнять только из серверных событий. Синтетические approve-rate — отдельный исследовательский показатель.

## Обновление: регистрация и доступ (2026-10-23)

Тумблер ролей удалён. `src/auth/` реализует локальные демо-регистрацию и вход. Тип аккаунта выбирается при регистрации; сотруднику нужен демонстрационный код приглашения. После входа используется роль сохранённого аккаунта; выбор роли на форме входа отсутствует. Переходы проверяются allowlist `canAccess`, компоненты кабинета размонтируются при выходе. Черновики теперь имеют ключ `alfa-credit-v1:{accountId}`. Старая анкета переносится только первому зарегистрированному предпринимателю; синтетическая лаборатория остаётся общим демо-стендом, не хранилищем клиентских данных.

Локальные аккаунты (salt + PBKDF2 SHA-256, 100000 итераций) хранятся в localStorage, id сессии — sessionStorage. Это прототип и не защищённая аутентификация: пользователь может изменить данные браузера. Публичный код ALFA-DEMO-BANK годится только для демонстрации. Реальные аккаунты и реальные банковские полномочия через него не выдавать.

Для рабочей версии нужны:

- `POST /auth/register`: регистрация только borrower, сервер назначает client; role из тела не доверять.
- `POST /auth/invitations/accept`: одноразовый непубличный токен, выданный администратором банка, привязанный к email, organisationId, permissions и сроку действия. Сервер атомарно гасит токен. Клиент не выбирает банковские permissions.
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`: сессия в HttpOnly Secure SameSite cookie, CSRF-защита, rate limit, Argon2id на сервере; роль и companyId/organisationId возвращает сервер.
- Все /bank/* требуют соответствующего bank permission; все клиентские ресурсы фильтруются по владению и tenant. Одной проверки role недостаточно. Прямой запрос чужого id должен давать 403/404.
- Выход инвалидирует сессию и очищает клиентский кеш; бэкенд не хранит персональные данные или токены в localStorage. Для банковских сотрудников предусмотреть корпоративный SSO/MFA.

Демо-форму заменить вызовами этих методов. Нельзя подключать реальные финансовые данные, сохранив localStorage-роль как источник полномочий.
