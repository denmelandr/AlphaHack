export type BusinessType = 'ИП' | 'ООО';
export type DocumentGuide = { id: string; title: string; desc: string; source: string; steps: string[]; checks: string[] };
export function documentList(type: string): DocumentGuide[] {
  return [
    { id: 'passport', title: 'Паспорт руководителя', desc: 'Разворот с фотографией и страница с регистрацией', source: 'Подготовьте читаемые копии нужных страниц.', steps: ['Для демонстрации используйте синтетический документ без персональных данных.', 'В рабочем сценарии подготовьте разворот с фотографией и страницу с регистрацией.', 'Сохраните страницы в одном PDF или изображении и добавьте файл в этот пункт.'], checks: ['Все края страниц видны', 'Текст читается, нет бликов и размытия', 'Загружен один файл PDF, JPG или PNG'] },
    { id: 'statement', title: 'Выписка по расчётному счёту', desc: 'За последние 6 месяцев — для оценки денежного потока', source: 'Получите файл в банке, где открыт расчётный счёт.', steps: ['Откройте расчётный счёт в интернет-банке.', 'Найдите раздел выписок или истории операций и выберите последние 6 месяцев.', 'Скачайте выписку в PDF. Название раздела и способ выгрузки зависят от вашего банка.'], checks: ['Указан нужный счёт и бизнес', 'Период охватывает 6 месяцев', 'Видны операции и остатки'] },
    { id: 'report', title: type === 'ИП' ? 'Налоговая декларация' : 'Бухгалтерская отчётность', desc: 'За последний завершённый отчётный год', source: 'Подготовьте файл вместе с бухгалтером или выгрузите его из вашей системы учёта.', steps: [type === 'ИП' ? 'Найдите подготовленную декларацию за последний завершённый отчётный год.' : 'Попросите бухгалтера подготовить бухгалтерскую отчётность за последний завершённый отчётный год.', 'Проверьте, что файл относится к вашему бизнесу и нужному периоду.', 'Сохраните документ в PDF и загрузите его. Если такого документа у бизнеса нет, уточните возможную замену у банка.'], checks: ['Совпадают название бизнеса и ИНН', 'Указан отчётный период', 'Все страницы на месте'] },
  ];
}

export function invalidateReport<T>(docs: Record<string, T>, currentType: string, nextType: string): Record<string, T> {
  if (currentType === nextType) return docs;
  const next = { ...docs };
  delete next.report;
  return next;
}

export type FitAnswers = { goal: string; channel: string; priority: string };
export const emptyAnswers: FitAnswers = { goal: '', channel: '', priority: '' };
export type ProductMatch = { id: string; title: string; purpose?: string; description: string; reason: string; kind: 'credit' | 'service' };
export function recommendProducts(answers: FitAnswers): ProductMatch[] {
  if (!answers.goal || !answers.channel || !answers.priority) return [];
  const credit: ProductMatch = answers.goal === 'equipment'
    ? { id: 'equipment', title: 'Финансирование оборудования', purpose: 'Оборудование', description: 'Категория финансирования для обновления техники и оснащения бизнеса.', reason: 'Вы планируете приобрести оборудование.', kind: 'credit' }
    : answers.goal === 'growth'
      ? { id: 'growth', title: 'Кредит на развитие', purpose: 'Развитие бизнеса', description: 'Категория кредита для расширения или нового направления.', reason: 'Вы хотите развивать бизнес.', kind: 'credit' }
      : { id: 'turnover', title: 'Кредит на оборотные средства', purpose: 'Пополнение оборотных средств', description: 'Категория финансирования текущих потребностей бизнеса.', reason: 'Вам нужно пополнить оборотные средства.', kind: 'credit' };
  const service: ProductMatch = answers.priority === 'reserve'
    ? { id: 'reserve', title: 'Продукты для свободного остатка', description: 'Обсудите с банком варианты для средств, которые не нужны на ближайшие платежи.', reason: 'Вы отметили наличие свободного остатка. Проверка подходящих продуктов и условий ещё не подключена.', kind: 'service' }
    : answers.priority === 'cashgap'
      ? { id: 'cashflow', title: 'Сервисы контроля денежного потока', description: 'Категория инструментов для планирования поступлений и расходов бизнеса.', reason: 'Вы хотите лучше контролировать денежный поток.', kind: 'service' }
    : answers.channel === 'online'
      ? { id: 'online-payments', title: 'Приём онлайн-платежей', description: 'Категория сервисов для оплаты на сайте и в интернет-магазине.', reason: 'Ваши клиенты покупают онлайн.', kind: 'service' }
      : answers.channel === 'offline'
        ? { id: 'acquiring', title: 'Эквайринг для торговой точки', description: 'Категория сервисов приёма платежей в вашей точке.', reason: 'Вы принимаете клиентов в офлайн-точке.', kind: 'service' }
        : { id: 'business-account', title: 'Расчётные сервисы для бизнеса', description: 'Категория сервисов для работы со счетами и платежами контрагентов.', reason: 'Вы работаете с другими компаниями.', kind: 'service' };
  return [credit, service];
}

export function repaymentModel(amount: number, rate: number, months: number, paidMonths: number) {
  const r = rate / 1200;
  const payment = r === 0 ? amount / months : amount * r / (1 - (1 + r) ** -months);
  const paid = Math.max(0, Math.min(months, Math.floor(paidMonths)));
  const balance = r === 0 ? amount - payment * paid : amount * (1 + r) ** paid - payment * ((1 + r) ** paid - 1) / r;
  return { payment, balance: Math.max(0, balance), remainingMonths: months - paid };
}
