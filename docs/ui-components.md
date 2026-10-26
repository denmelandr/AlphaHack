# Использованные UI-компоненты

## shadcn/ui + Radix

Структура Dialog, Dropdown Menu и Tooltip адаптирована из официального shadcn registry под существующий CSS без глобального Tailwind preflight. Установлены настоящие Radix-примитивы; клавиатура, порталы, позиционирование, focus trap и закрытие реализованы ими.

- `src/components/ui/dialog.tsx`: все окна профиля, реквизитов, помощи, уведомлений и графика.
- `src/Dropdown.tsx`: меню аватарки и бизнеса; позиционирование учитывает края viewport.
- `src/components/ui/tooltip.tsx`: объяснения дополнительной прибыли и эффекта после процентов. Открываются по наведению, фокусу и нажатию.
- `src/components/ui/scenario-tabs.tsx`: Radix Tabs с настоящими tab/tabpanel и управлением стрелками клавиатуры.

Источники:
- https://ui.shadcn.com/r/styles/new-york/dialog.json
- https://ui.shadcn.com/r/styles/new-york/dropdown-menu.json
- https://ui.shadcn.com/r/styles/new-york/tooltip.json

## Animate UI + Motion

Установлен `@animate-ui/react` и использован настоящий CountingNumber для платежа и эффекта. Числа стартуют с текущего значения; изменения анимируются коротким переходом 0.4 с. Доступное имя содержит итоговую сумму, а не каждый промежуточный кадр. Animate UI учитывает reduced motion; для Motion задан reducedMotion=user.

Источник: https://animate-ui.com/docs/primitives/animate-ui/counting-number

## Fluid Functionalism

Скользящий индикатор сценариев вдохновлён Tabs из Fluid Functionalism. Реализация оригинальная: Radix Tabs + Motion layoutId. Из Fluid не копировались исходники и не устанавливался пакет.

Источник: https://www.fluidfunctionalism.com/docs/tabs

Badtz UI рассмотрен как референс, его компоненты не включены. Изменения не добавляют новую бизнес-логику или банковские интеграции. Размеры текста и фирменная палитра сохраняются. Лицензии компонентов находятся в docs/licenses и перечислены в THIRD_PARTY_NOTICES.
