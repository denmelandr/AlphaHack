# Third-party notices

Неофициальный прототип хакатона. Название и визуальная идентичность Альфа-Банка принадлежат правообладателям; включение Core DS не означает официальную поддержку продукта. Кейс и исследовательские изображения предоставлены командой.

## Frontend

Разрешённые версии всех пакетов, включая транзитивные, зафиксированы в корневом `pnpm-lock.yaml`. Сводка прямых зависимостей:

| Компонент | Версия / источник | Лицензия / примечание |
|---|---|---|
| React / React DOM | 19.0.0, Meta и участники | MIT |
| TypeScript | 5.7.2, Microsoft | Apache-2.0 |
| Vite | 6.0.5, Evan You и участники | MIT |
| Lucide React | 0.468.0 | ISC; производные Feather — MIT |
| Alfa Core Components Button | диапазон ^13.2.4, точная версия в lock | MIT; core-ds/core-components |
| Radix Dialog / Dropdown / Tabs / Tooltip | точные версии в lock | MIT; [текст](docs/licenses/radix-ui.txt) |
| Motion | диапазон ^14.5.0, точная версия в lock | MIT; [текст](docs/licenses/motion.txt) |
| Animate UI React | диапазон ^2.0.0, точная версия в lock | MIT с Commons Clause; это дополнительное ограничение, [текст](docs/licenses/animate-ui.txt) |
| shadcn/ui | адаптированные структуры компонентов | MIT; [текст](docs/licenses/shadcn-ui.txt) |
| Manrope | Mikhail Sharanda / Mirko Velimirovic | SIL Open Font License 1.1; загрузка через Google Fonts |

Fluid Functionalism использован как визуальный референс, код и пакет не скопированы. Badtz UI рассматривался как референс, в поставку не включён. Старый отдельный frontend и его зависимости удалены; `react-router-dom` не является прямой зависимостью текущего приложения.

## Backend и инструменты

Версии прямых Python-зависимостей заданы через `==` в `credit-conveyor/backend/requirements.txt` и `credit-conveyor/integrations-mock/requirements.txt`. Транзитивные Python-зависимости могут обновляться при новой сборке. Лицензии транзитивных пакетов сохраняются в установленных дистрибутивах.

| Компонент | Лицензия |
|---|---|
| FastAPI, SQLAlchemy, Alembic, Pydantic, pydantic-settings | MIT |
| Uvicorn | BSD-3-Clause |
| psycopg 3 | LGPL-3.0; бинарная поставка включает собственные notices |
| python-jose | MIT |
| passlib | BSD |
| bcrypt | Apache-2.0 |
| redis-py | MIT |
| httpx | BSD-3-Clause |
| PyYAML | MIT |
| email-validator | The Unlicense |
| pytest | MIT |
| python-multipart | Apache-2.0 |

## Инфраструктура и документация

Python 3.12 (PSF), Node.js 22 (MIT и включённые notices), nginx (BSD-подобная лицензия), PostgreSQL 16 (PostgreSQL License), pnpm 10.11.0 (MIT). Базовые Linux-образы содержат дополнительные пакеты с собственными лицензиями. Docker image tags описаны в Dockerfile/Compose и не закреплены по digest.

Redis поставляется образом `redis:7-alpine`; лицензия зависит от разрешённой версии (для Redis 7.4 — RSALv2 / SSPLv1). Не следует считать весь диапазон Redis 7 BSD-лицензированным. Условия проверяются по фактическому образу при распространении.

FastAPI Swagger UI использует Swagger UI (Apache-2.0), ReDoc — MIT. UI-ресурсы по умолчанию загружаются с внешнего CDN. GitHub Actions использует actions/checkout, actions/setup-node и pnpm/action-setup на условиях их upstream-проектов.

## Модели и датасеты

В стандартной поставке языковая модель не запускается: `LLM_ENABLED=false`. Копилот использует шаблоны, аномалии определяются правилами. Скоринг и политика — собственные детерминированные правила, не обученная ML-модель; показатели PD/вероятности учебные и не валидированы на банковской истории.

Опционально конфигурация предусматривает `qwen2.5:7b-instruct` через Ollama (MIT). Модель Qwen2.5-7B-Instruct опубликована Qwen / Alibaba Cloud с открытыми весами под Apache-2.0: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct. Веса не включены в репозиторий и скачиваются отдельно. Другие модели в проверяемой конфигурации не используются.

Внешних обучающих датасетов нет. Компании, транзакции, кредитные истории и документы seed синтетические; они создаются кодом `services/seed.py` и `integrations-mock/main.py`.

## Смоделированные интеграции

| Источник | Что моделирует |
|---|---|
| БКИ | рейтинг, просрочки и долговую нагрузку |
| ЕГРЮЛ/ЕГРИП | статус, возраст и признаки компании |
| ФНС | налоги и блокировку счёта |
| ОФД | выручку и поток чеков |
| Дебиторка / контрагенты | неоплаченные счета и риск должников |

Все эти источники — локальный `integrations-mock`, а не реальные API организаций. 1С/Эльба и Ozon/WB не подключены. Выдача денег, ПЭП, автопилот и финансовые действия моделируются; реальные сообщения не отправляются. Загрузка и скачивание файлов, авторизация и сохранение состояния в PostgreSQL при этом реализованы.

Эта сводка не заменяет полные upstream-лицензии каждого пакета.
