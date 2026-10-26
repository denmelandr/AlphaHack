# Чек-лист сдачи

## Артефакты

| Требование | Материал | Состояние |
|---|---|---|
| GitHub и история | https://github.com/denmelandr/AlphaHack | Репозиторий опубликован, логические коммиты сохранены |
| Однозначная ревизия | `git rev-parse HEAD`, `VERSION` | Hash нужно указать при фактической сдаче; release tag отдельно не создан |
| Доступ жюри | GitHub Settings → Collaborators | Владелец должен подтвердить доступ `alfa-hack-2026`, если репозиторий приватный |
| Docker и единая команда | `compose.yaml`, Dockerfile, README | Есть |
| Версии | `pnpm-lock.yaml`, `requirements.txt`, Docker tags | Основные версии зафиксированы; Python transitives и image digests не закреплены полностью |
| README | `README.md` | Назначение, окружение, запуск, env, ограничения, сценарии |
| Синтетика и доступы | seed, README, `SYNTHETIC_DATA.md` | Есть |
| Сторонние компоненты и моки | `THIRD_PARTY_NOTICES.md` | Есть |
| Архитектура, состояния и данные | `docs/architecture.md` | Mermaid и ERD |
| API / Swagger / OpenAPI | `docs/api.md`, `docs/openapi.json`, `/docs` | Есть |
| Коллекция запросов | `docs/postman_collection.json` | Проверяется скриптом из `scripts/` |
| Тесты и демонстрация | `docs/test-scenarios.md`, `docs/demo.md` | Автоматические API/unit + ручной UI-сценарий |

## Финальная проверка

Из корня:

```sh
docker compose config --quiet
docker compose up --build -d
bash scripts/verify_submission.sh
python3 scripts/run_collection.py
```

После проверки интерфейса по `docs/demo.md` выполните `git status --short` и `git rev-parse HEAD`. Передайте жюри URL репозитория и hash проверенной версии. Если используете tag, создайте его после всех финальных изменений и отправьте отдельно.

Запуск на текущей машине и успешные тесты не заменяют проверку **с чистого clone на другом компьютере**. Эту проверку нужно провести перед дедлайном. Облачная публикация необязательна. GPU, платные API и реальные банковские данные для базового запуска не нужны.
