
export enum TenderStatus {
  OPEN = 'Прием заявок',
  REVIEW = 'Работа комиссии',
  CLOSED = 'Завершена',
  DRAFT = 'Анонс'
}

export enum Category {
  LOGISTICS = 'Логистика и склад',
  IT = 'IT и Телеком',
  CONSTRUCTION = 'Строительство и ремонт',
  MARKETING = 'Маркетинг и реклама',
  OFFICE = 'Хозяйственные нужды',
  EQUIPMENT = 'Оборудование'
}

export enum ProcurementMethod {
  AUCTION = 'Электронный аукцион',
  REQUEST_PROPOSAL = 'Запрос котировок',
  TENDER = 'Открытый тендер',
  PURCHASE_SMALL = 'Закупка малого объема'
}

export interface Tender {
  id: string;
  title: string;
  category: Category;
  method: ProcurementMethod;
  description: string;
  budget: number;
  currency: string;
  deadline: string;
  publishedAt: string;
  status: TenderStatus;
  organizer: string;
  region: string;
  documents: string[];
  tags: string[];
}

export interface NewsItem {
  id: string;
  date: string;
  title: string;
  summary: string;
  category: string;
  image?: string;
}

export interface AIAnalysisResult {
  summary: string;
  keyRequirements: string[];
  riskAssessment: string;
  suggestedBidRange: string;
}
