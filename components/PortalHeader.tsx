
import React from 'react';

const PortalHeader: React.FC<{ setView: (v: string) => void }> = ({ setView }) => {
  return (
    <header className="portal-header sticky top-0 z-50 bg-white border-b border-gray-100 w-full">
      <div className="bg-gray-50/50 py-1.5 border-b border-gray-100 w-full px-6">
        <div className="max-w-7xl mx-auto flex justify-between items-center text-[10px] font-bold text-gray-400 uppercase tracking-widest">
          <div className="flex gap-6">
            <span className="cursor-pointer hover:text-purple-600 transition-colors">Обучение</span>
            <span className="cursor-pointer hover:text-purple-600 transition-colors">Помощь</span>
            <span className="cursor-pointer hover:text-purple-600 transition-colors">Контакты</span>
          </div>
          <div className="flex gap-6 items-center">
            <span className="opacity-60">Техподдержка: 8 800 555-55-55</span>
            <span className="text-purple-600 font-black cursor-pointer">RU</span>
          </div>
        </div>
      </div>
      
      <div className="w-full px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-10">
            <div 
              className="cursor-pointer flex items-center group" 
              onClick={() => setView('home')}
            >
              <div className="w-9 h-9 wb-gradient rounded-lg flex items-center justify-center text-white font-black text-lg mr-3 shadow-sm group-hover:scale-105 transition-transform">W</div>
              <div>
                <h1 className="text-base font-black text-gray-900 leading-none tracking-tight">WB.TENDER</h1>
                <p className="text-[9px] text-gray-400 font-bold uppercase mt-0.5">Портал закупок</p>
              </div>
            </div>
            
            <nav className="hidden lg:flex items-center gap-6">
              <button onClick={() => setView('home')} className="text-[12px] font-bold text-gray-600 hover:text-purple-600 py-2 border-b-2 border-transparent hover:border-purple-600 transition-all uppercase tracking-wide">Закупки</button>
              <button onClick={() => setView('suppliers')} className="text-[12px] font-bold text-gray-600 hover:text-purple-600 py-2 border-b-2 border-transparent hover:border-purple-600 transition-all uppercase tracking-wide">Поставщикам</button>
              <button onClick={() => setView('analytics')} className="text-[12px] font-bold text-gray-600 hover:text-purple-600 py-2 border-b-2 border-transparent hover:border-purple-600 transition-all uppercase tracking-wide">Реестры</button>
              <button onClick={() => setView('news')} className="text-[12px] font-bold text-gray-600 hover:text-purple-600 py-2 border-b-2 border-transparent hover:border-purple-600 transition-all uppercase tracking-wide">Новости</button>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => setView('profile')}
              className="px-4 py-2 text-[11px] font-black text-gray-600 hover:bg-gray-100 rounded-xl transition-all border border-gray-200 uppercase tracking-widest"
            >
              Личный кабинет
            </button>
            <button className="px-4 py-2 text-[11px] font-black btn-primary rounded-xl uppercase tracking-widest shadow-lg shadow-purple-100">Регистрация</button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default PortalHeader;
