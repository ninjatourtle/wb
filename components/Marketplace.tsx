
import React, { useState, useMemo } from 'react';
import { MOCK_TENDERS } from '../constants';
import { Tender, TenderStatus, Category } from '../types';

const ITEMS_PER_PAGE = 5;

const Marketplace: React.FC<{ onSelect: (t: Tender) => void }> = ({ onSelect }) => {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('Все');
  const [statusFilter, setStatusFilter] = useState<string>('Все');
  const [regionFilter, setRegionFilter] = useState<string>('Все');
  const [sortBy, setSortBy] = useState<string>('date_desc');
  const [currentPage, setCurrentPage] = useState(1);

  const regions = useMemo(() => ['Все', ...Array.from(new Set(MOCK_TENDERS.map(t => t.region)))], []);

  const filteredAndSorted = useMemo(() => {
    let result = MOCK_TENDERS.filter(t => {
      const matchesSearch = t.title.toLowerCase().includes(search.toLowerCase()) || t.id.toLowerCase().includes(search.toLowerCase());
      const matchesCategory = categoryFilter === 'Все' || t.category === categoryFilter;
      const matchesStatus = statusFilter === 'Все' || t.status === statusFilter;
      const matchesRegion = regionFilter === 'Все' || t.region === regionFilter;
      return matchesSearch && matchesCategory && matchesStatus && matchesRegion;
    });

    result.sort((a, b) => {
      switch (sortBy) {
        case 'budget_asc': return a.budget - b.budget;
        case 'budget_desc': return b.budget - a.budget;
        case 'deadline': return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
        default: return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
      }
    });

    return result;
  }, [search, categoryFilter, statusFilter, regionFilter, sortBy]);

  const totalPages = Math.ceil(filteredAndSorted.length / ITEMS_PER_PAGE);
  const paginatedTenders = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredAndSorted.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredAndSorted, currentPage]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="w-full px-6 py-8">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-8 overflow-hidden relative w-full">
        <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-purple-50/30 rounded-full -mr-20 -mt-20 z-0 pointer-events-none"></div>
        <div className="relative z-10 w-full">
          <h2 className="text-2xl font-black text-gray-900 mb-2 tracking-tight">Единый реестр закупок</h2>
          <p className="text-sm text-gray-400 mb-6 font-medium">Актуальные лоты группы компаний Wildberries</p>
          
          <div className="flex flex-col md:flex-row gap-3">
            <div className="flex-1">
              <input 
                type="text" 
                placeholder="Поиск по номеру, названию или предмету..." 
                className="w-full px-5 py-3.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-100 focus:border-purple-600 transition-all outline-none text-gray-800 text-sm font-medium"
                value={search}
                onChange={e => { setSearch(e.target.value); setCurrentPage(1); }}
              />
            </div>
            <button className="btn-primary px-10 py-3.5 rounded-xl font-black text-sm uppercase tracking-widest shadow-md">
              Найти
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 w-full">
        <aside className="lg:w-72 flex-shrink-0">
          <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm sticky top-28">
            <h3 className="font-black text-gray-900 mb-6 flex items-center text-xs uppercase tracking-widest opacity-60">Фильтрация</h3>
            
            <div className="mb-6">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Категория</p>
              <div className="space-y-2">
                {['Все', ...Object.values(Category)].map(cat => (
                  <label key={cat} className="flex items-center group cursor-pointer">
                    <div className={`w-4 h-4 rounded border-2 mr-3 flex items-center justify-center transition-all ${categoryFilter === cat ? 'bg-purple-600 border-purple-600 shadow-sm' : 'border-gray-200'}`}>
                      {categoryFilter === cat && <div className="w-1.5 h-1.5 bg-white rounded-full"></div>}
                    </div>
                    <input type="radio" className="hidden" checked={categoryFilter === cat} onChange={() => { setCategoryFilter(cat); setCurrentPage(1); }} />
                    <span className={`text-[13px] font-bold ${categoryFilter === cat ? 'text-purple-700' : 'text-gray-500 group-hover:text-purple-600'}`}>{cat}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="mb-6">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Регион</p>
              <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin pr-2">
                {regions.map(region => (
                  <label key={region} className="flex items-center group cursor-pointer">
                    <div className={`w-4 h-4 rounded border-2 mr-3 flex items-center justify-center transition-all ${regionFilter === region ? 'bg-purple-600 border-purple-600 shadow-sm' : 'border-gray-200'}`}>
                      {regionFilter === region && <div className="w-1.5 h-1.5 bg-white rounded-full"></div>}
                    </div>
                    <input type="radio" className="hidden" checked={regionFilter === region} onChange={() => { setRegionFilter(region); setCurrentPage(1); }} />
                    <span className={`text-[13px] font-bold ${regionFilter === region ? 'text-purple-700' : 'text-gray-500 group-hover:text-purple-600'}`}>{region}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <section className="flex-1 space-y-4">
          <div className="flex justify-between items-center px-2 mb-2">
            <p className="text-[11px] font-black text-gray-400 uppercase tracking-widest">Лотов: <span className="text-gray-900">{filteredAndSorted.length}</span></p>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-gray-400 font-black uppercase tracking-widest">Сортировка:</span>
              <select value={sortBy} onChange={(e) => { setSortBy(e.target.value); setCurrentPage(1); }} className="bg-transparent border-none text-[12px] font-black text-gray-900 outline-none cursor-pointer uppercase tracking-wide">
                <option value="date_desc">Новые</option>
                <option value="budget_desc">Цена ↓</option>
                <option value="budget_asc">Цена ↑</option>
                <option value="deadline">Срок</option>
              </select>
            </div>
          </div>

          {paginatedTenders.length > 0 ? (
            <div className="space-y-4">
              {paginatedTenders.map(t => (
                <div key={t.id} onClick={() => onSelect(t)} className="bg-white border border-gray-100 rounded-xl p-6 hover:shadow-xl transition-all cursor-pointer group relative">
                  <div className="flex flex-col md:flex-row gap-6">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-3">
                        <span className="px-2.5 py-1 bg-gray-50 text-gray-400 text-[9px] font-black rounded border border-gray-100 uppercase tracking-widest">{t.id}</span>
                        <span className="px-2.5 py-1 bg-purple-50 text-purple-600 text-[9px] font-black rounded uppercase tracking-widest border border-purple-100">{t.method}</span>
                      </div>
                      <h3 className="text-lg font-black text-gray-800 group-hover:text-purple-600 transition-colors mb-4">{t.title}</h3>
                      <div className="flex gap-10">
                        <div>
                          <p className="text-[9px] text-gray-400 uppercase font-black mb-1">Регион</p>
                          <p className="text-[13px] font-bold text-gray-700">{t.region}</p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-400 uppercase font-black mb-1">Срок</p>
                          <p className="text-[13px] font-bold text-gray-700">{t.deadline}</p>
                        </div>
                      </div>
                    </div>
                    <div className="md:w-56 flex flex-col md:items-end justify-between border-t md:border-t-0 md:border-l border-gray-100 pt-4 md:pt-0 md:pl-6">
                      <div className="md:text-right">
                        <p className="text-[9px] uppercase text-gray-400 font-black mb-1">Бюджет (НМЦ)</p>
                        <p className="text-xl font-black text-gray-900">{new Intl.NumberFormat('ru-RU', { style: 'currency', currency: t.currency, maximumFractionDigits: 0 }).format(t.budget)}</p>
                      </div>
                      <div className="mt-4 md:mt-0 flex flex-col md:items-end">
                        <span className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase mb-3 text-white ${t.status === TenderStatus.OPEN ? 'bg-green-500' : 'bg-gray-400'}`}>{t.status}</span>
                        <span className="text-[11px] font-black text-purple-600 uppercase tracking-widest group-hover:translate-x-1 transition-transform">Подробнее →</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {totalPages > 1 && (
                <div className="flex justify-center items-center gap-2 pt-6">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                    <button key={page} onClick={() => handlePageChange(page)} className={`w-9 h-9 rounded-lg border font-black text-xs transition-all ${currentPage === page ? 'bg-purple-600 border-purple-600 text-white shadow-lg shadow-purple-100' : 'bg-white text-gray-500 border-gray-100 hover:border-purple-200'}`}>
                      {page}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-2xl p-16 text-center border border-gray-100 shadow-sm w-full">
              <p className="text-xl font-black text-gray-900 mb-2">Лоты не найдены</p>
              <button onClick={() => { setSearch(''); setCategoryFilter('Все'); setStatusFilter('Все'); setRegionFilter('Все'); setCurrentPage(1); }} className="mt-4 text-[12px] text-purple-600 font-black uppercase tracking-widest border-b-2 border-purple-100 hover:border-purple-600 transition-all">Сбросить фильтры</button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default Marketplace;
