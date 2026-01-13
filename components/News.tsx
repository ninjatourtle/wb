
import React from 'react';
import { MOCK_NEWS } from '../constants';

const News: React.FC = () => {
  return (
    <div className="w-full px-6 md:px-10 py-10 animate-in fade-in duration-500">
      <div className="mb-10">
        <h2 className="text-3xl font-black text-gray-900 tracking-tight">Новости платформы</h2>
        <p className="text-sm text-gray-400 font-medium mt-1">Официальные уведомления и обновления для партнеров</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {MOCK_NEWS.map(news => (
          <div key={news.id} className="bg-white rounded-2xl border border-gray-100 overflow-hidden hover:shadow-xl transition-all group flex flex-col">
            <div className="p-8 flex-1">
              <div className="flex justify-between items-center mb-6">
                <span className="px-3 py-1 bg-purple-50 text-purple-600 text-[9px] font-black rounded uppercase tracking-widest border border-purple-100">{news.category}</span>
                <span className="text-[10px] text-gray-300 font-black uppercase tracking-widest">{news.date}</span>
              </div>
              <h3 className="text-xl font-black text-gray-900 mb-4 group-hover:text-purple-600 transition-colors leading-tight">{news.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed font-medium mb-6">{news.summary}</p>
            </div>
            <div className="px-8 pb-8">
              <button className="text-[11px] font-black text-purple-600 uppercase tracking-widest group-hover:translate-x-1 transition-transform inline-flex items-center">
                Читать полностью <span className="ml-2">→</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-16 bg-gray-900 rounded-[40px] p-12 text-white relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-10">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
        <div className="relative z-10 max-w-xl text-center md:text-left">
          <h3 className="text-3xl font-black mb-4 tracking-tight">Подпишитесь на уведомления</h3>
          <p className="text-gray-400 text-lg leading-relaxed font-medium">Будьте первым, кто узнает о новых тендерах и изменениях в регламенте Wildberries Sourcing.</p>
        </div>
        <div className="relative z-10 w-full md:w-auto">
          <div className="flex bg-white/10 p-2 rounded-2xl border border-white/10 backdrop-blur-md">
            <input type="email" placeholder="E-mail адрес..." className="bg-transparent text-white px-6 py-4 outline-none placeholder:text-gray-500 text-sm font-bold w-full md:w-72" />
            <button className="wb-gradient px-8 py-4 rounded-xl text-[12px] font-black uppercase tracking-widest shadow-2xl">Ок</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default News;
