
import React, { useState } from 'react';
import PortalHeader from './components/PortalHeader';
import Marketplace from './components/Marketplace';
import TenderDetails from './components/TenderDetails';
import Dashboard from './components/Dashboard';
import News from './components/News';
import { Tender } from './types';

const App: React.FC = () => {
  const [view, setView] = useState('home');
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);

  const renderContent = () => {
    if (selectedTender) {
      return <TenderDetails tender={selectedTender} onBack={() => setSelectedTender(null)} />;
    }

    switch (view) {
      case 'home':
        return <Marketplace onSelect={setSelectedTender} />;
      case 'analytics':
        return <Dashboard isProfile={false} />;
      case 'profile':
        return <Dashboard isProfile={true} />;
      case 'news':
        return <News />;
      case 'suppliers':
        return (
          <div className="w-full py-20 px-6 text-center bg-white min-h-[60vh] flex flex-col justify-center">
            <div className="max-w-4xl mx-auto">
              <h2 className="text-3xl font-black text-gray-900 mb-6 tracking-tight">Станьте стратегическим партнером Wildberries</h2>
              <p className="text-sm text-gray-400 mb-10 leading-relaxed font-medium">
                Мы приглашаем к долгосрочному сотрудничеству надежных поставщиков со всей страны. 
                Прозрачные условия, электронный документооборот и гарантированные объемы заказов.
              </p>
              <div className="grid md:grid-cols-3 gap-6 mb-16">
                <div className="bg-gray-50 p-8 rounded-3xl border border-gray-100 shadow-sm">
                  <div className="text-4xl mb-4">📋</div>
                  <h3 className="text-xs font-black mb-2 text-gray-900 uppercase tracking-widest">Аккредитация</h3>
                  <p className="text-xs text-gray-500 leading-relaxed font-medium">Быстрая цифровая проверка вашей компании.</p>
                </div>
                <div className="bg-gray-50 p-8 rounded-3xl border border-gray-100 shadow-sm">
                  <div className="text-4xl mb-4">💎</div>
                  <h3 className="text-xs font-black mb-2 text-gray-900 uppercase tracking-widest">Прямые торги</h3>
                  <p className="text-xs text-gray-500 leading-relaxed font-medium">Без посредников. Только прямое взаимодействие.</p>
                </div>
                <div className="bg-gray-50 p-8 rounded-3xl border border-gray-100 shadow-sm">
                  <div className="text-4xl mb-4">📈</div>
                  <h3 className="text-xs font-black mb-2 text-gray-900 uppercase tracking-widest">Развитие</h3>
                  <p className="text-xs text-gray-500 leading-relaxed font-medium">Масштабируйте бизнес по всей стране.</p>
                </div>
              </div>
              <button className="btn-primary px-12 py-4 rounded-xl font-black text-xs uppercase tracking-[0.2em] shadow-2xl shadow-purple-100">Подать заявку</button>
            </div>
          </div>
        );
      default:
        return <Marketplace onSelect={setSelectedTender} />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col w-full bg-gray-50/50">
      <PortalHeader setView={(v) => { setView(v); setSelectedTender(null); }} />
      <main className="flex-1 w-full flex flex-col items-center">
        <div className="w-full max-w-7xl">
          {renderContent()}
        </div>
      </main>
      
      <footer className="bg-gray-900 text-gray-500 py-12 px-6 w-full flex flex-col items-center">
        <div className="w-full max-w-7xl">
          <div className="w-full grid grid-cols-1 md:grid-cols-5 gap-10">
            <div className="md:col-span-2">
              <div className="flex items-center mb-4">
                <div className="w-7 h-7 wb-gradient rounded-lg flex items-center justify-center text-white font-black text-sm mr-3 shadow-lg">W</div>
                <span className="text-white font-black text-lg tracking-tighter">WB.TENDER</span>
              </div>
              <p className="text-xs leading-relaxed mb-6 max-w-sm font-medium opacity-60">
                Официальная высокотехнологичная площадка для проведения всех типов закупок группы компаний Wildberries. 
              </p>
            </div>
            <div>
              <h4 className="text-white font-black mb-4 uppercase text-[9px] tracking-[0.3em] opacity-30">Платформа</h4>
              <ul className="text-[11px] space-y-2 font-bold uppercase tracking-wide">
                <li className="hover:text-white cursor-pointer transition-colors">О портале</li>
                <li className="hover:text-white cursor-pointer transition-colors">Регламент</li>
                <li className="hover:text-white cursor-pointer transition-colors">Документы</li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-black mb-4 uppercase text-[9px] tracking-[0.3em] opacity-30">Поддержка</h4>
              <ul className="text-[11px] space-y-2 font-bold uppercase tracking-wide">
                <li className="hover:text-white cursor-pointer transition-colors">Помощь</li>
                <li className="hover:text-white cursor-pointer transition-colors">Техподдержка</li>
                <li className="hover:text-white cursor-pointer transition-colors">Контакты</li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-black mb-4 uppercase text-[9px] tracking-[0.3em] opacity-30">Новости</h4>
              <ul className="text-[11px] space-y-2 font-bold uppercase tracking-wide">
                <li className="hover:text-white cursor-pointer transition-colors">Пресс-центр</li>
                <li className="hover:text-white cursor-pointer transition-colors">Аналитика</li>
                <li className="hover:text-white cursor-pointer transition-colors">Блог</li>
              </ul>
            </div>
          </div>
          <div className="w-full mt-12 pt-6 border-t border-white/5 text-[9px] flex flex-col md:flex-row justify-between items-center gap-4 font-black uppercase tracking-[0.2em]">
            <span className="opacity-40">© 2024 Wildberries Procurement. Все права защищены.</span>
            <div className="flex gap-8">
              <span className="hover:text-white cursor-pointer opacity-60">Карта сайта</span>
              <span className="hover:text-white cursor-pointer text-red-500 opacity-80">Комплаенс</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
