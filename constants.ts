
import { Tender, TenderStatus, Category, ProcurementMethod, NewsItem } from './types';

export const MOCK_TENDERS: Tender[] = [
  {
    id: 'WB-2024-0451',
    title: 'Строительство автоматизированного сортировочного центра в Казани (Этап 2)',
    category: Category.CONSTRUCTION,
    method: ProcurementMethod.TENDER,
    description: 'Полный комплекс строительно-монтажных работ по возведению второй очереди складского комплекса. Требуется опыт работы с объектами площадью от 30 тыс. кв.м.',
    budget: 450000000,
    currency: 'RUB',
    publishedAt: '2024-05-20',
    deadline: '2024-12-30',
    status: TenderStatus.OPEN,
    organizer: 'ООО "Вайлдберриз"',
    region: 'Республика Татарстан',
    documents: ['проектная_документация.zip', 'чертежи_архитектура.pdf'],
    tags: ['Генподряд', 'Склад', 'Казань']
  },
  {
    id: 'WB-2024-0892',
    title: 'Поставка серверного оборудования для ЦОД (импортозамещение)',
    category: Category.IT,
    method: ProcurementMethod.AUCTION,
    description: 'Поставка и пусконаладка стоечных серверов отечественного производства (в реестре Минпромторга) для расширения вычислительных мощностей.',
    budget: 125000000,
    currency: 'RUB',
    publishedAt: '2024-05-22',
    deadline: '2024-06-15',
    status: TenderStatus.REVIEW,
    organizer: 'WB Tech Lab',
    region: 'г. Москва',
    documents: ['спецификация.xlsx'],
    tags: ['Серверы', 'IT', 'Минпромторг']
  },
  {
    id: 'WB-2024-0120',
    title: 'Закупка упаковочных материалов (стрейч-пленка, гофрокороба)',
    category: Category.OFFICE,
    method: ProcurementMethod.REQUEST_PROPOSAL,
    description: 'Обеспечение расходными материалами складов Центрального федерального округа на 3-й квартал 2024 года.',
    budget: 12000000,
    currency: 'RUB',
    publishedAt: '2024-05-24',
    deadline: '2024-06-05',
    status: TenderStatus.OPEN,
    organizer: 'Департамент снабжения',
    region: 'Московская область',
    documents: ['график_поставок.pdf', 'образцы.jpg'],
    tags: ['Упаковка', 'Расходники', 'Склад']
  },
  {
    id: 'WB-2024-0333',
    title: 'Услуги по аудиту информационной безопасности',
    category: Category.IT,
    method: ProcurementMethod.TENDER,
    description: 'Проведение внешнего пентеста и аудита систем безопасности в соответствии со стандартом PCI DSS.',
    budget: 4500000,
    currency: 'RUB',
    publishedAt: '2024-05-10',
    deadline: '2024-05-25',
    status: TenderStatus.CLOSED,
    organizer: 'Департамент ИБ',
    region: 'РФ (Дистанционно)',
    documents: ['тз_аудит.pdf'],
    tags: ['Безопасность', 'Аудит', 'ПО']
  }
];

export const MOCK_NEWS: NewsItem[] = [
  {
    id: '1',
    date: '20.05.2024',
    title: 'Wildberries расширяет программу поддержки малого бизнеса',
    summary: 'Новые условия кредитования и упрощенная процедура аккредитации для региональных поставщиков.',
    category: 'События'
  },
  {
    id: '2',
    date: '18.05.2024',
    title: 'Обновление регламента электронных торгов',
    summary: 'С 1 июня вступают в силу изменения в правилах подачи ценовых предложений в аукционах.',
    category: 'Регламент'
  },
  {
    id: '3',
    date: '15.05.2024',
    title: 'Новый складской хаб в Екатеринбурге',
    summary: 'Запущена первая очередь тендеров на логистическое обслуживание нового логистического центра.',
    category: 'Закупки'
  }
];
