
import React, { useState } from 'react';
import { Tender, TenderStatus } from '../types';

interface BidModalProps {
  tender: Tender;
  onClose: () => void;
}

const BidModal: React.FC<BidModalProps> = ({ tender, onClose }) => {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-900/70 backdrop-blur-md">
      <div className="bg-white rounded-[24px] w-full max-w-lg p-8 shadow-2xl animate-in zoom-in-95 duration-200">
        <div className="flex justify-between items-start mb-6 border-b border-gray-100 pb-4">
          <div>
            <h3 className="text-xl font-black text-gray-900 mb-1">Подача предложения</h3>
            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Лот: {tender.id}</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-gray-50 flex items-center justify-center hover:bg-gray-100 transition-colors text-gray-400">✕</button>
        </div>
        
        <form className="space-y-5">
          <div>
            <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1.5">Предлагаемая цена (₽, без НДС)</label>
            <input 
              type="number" 
              placeholder="0.00" 
              className="w-full px-4 py-3 rounded-xl border border-gray-200 font-black text-base focus:ring-4 focus:ring-purple-50 focus:border-purple-600 transition-all outline-none" 
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1.5">Комментарий к предложению</label>
            <textarea 
              rows={3} 
              placeholder="Опишите особенности вашего предложения..." 
              className="w-full px-4 py-3 rounded-xl border border-gray-200 font-medium text-xs focus:ring-4 focus:ring-purple-50 focus:border-purple-600 transition-all outline-none resize-none"
            ></textarea>
          </div>
          <div className="p-6 border-2 border-dashed border-gray-100 rounded-xl text-center hover:border-purple-200 transition-colors cursor-pointer bg-gray-50/50 group">
            <span className="text-xl mb-1 block group-hover:scale-110 transition-transform">📁</span>
            <p className="text-[11px] font-bold text-gray-500">Прикрепить файлы ТКП</p>
            <p className="text-[9px] text-gray-400 mt-0.5 uppercase font-black tracking-tighter">PDF, XLSX или ZIP до 50 МБ</p>
          </div>
          <div className="flex items-center gap-2 mb-2">
            <input type="checkbox" id="terms" className="w-4 h-4 rounded text-purple-600" />
            <label htmlFor="terms" className="text-[10px] font-medium text-gray-500 leading-none">Я подтверждаю согласие с регламентом проведения торгов WB</label>
          </div>
          <button 
            type="button" 
            onClick={() => { alert('Ваше предложение успешно отправлено в систему ЭДО!'); onClose(); }} 
            className="w-full wb-gradient py-4 rounded-xl text-white font-black uppercase tracking-widest shadow-xl shadow-purple-100 hover:scale-[1.02] active:scale-[0.98] transition-all text-xs"
          >
            Подписать и отправить
          </button>
        </form>
      </div>
    </div>
  );
};

interface TenderDetailsProps {
  tender: Tender;
  onBack: () => void;
}

const TenderDetails: React.FC<TenderDetailsProps> = ({ tender, onBack }) => {
  const [showModal, setShowModal] = useState(false);

  const stages = [
    { title: 'Публикация', date: tender.publishedAt, isCompleted: true },
    { title: 'Прием заявок', date: `до ${tender.deadline}`, isCompleted: tender.status !== TenderStatus.OPEN, isActive: tender.status === TenderStatus.OPEN },
    { title: 'Комиссия', date: 'Ожидание', isActive: tender.status === TenderStatus.REVIEW },
    { title: 'Итоги', date: 'Ожидание', isCompleted: tender.status === TenderStatus.CLOSED }
  ];

  return (
    <div className="w-full px-6 py-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {showModal && <BidModal tender={tender} onClose={() => setShowModal(false)} />}
      
      <button onClick={onBack} className="mb-6 text-[10px] text-purple-600 font-black flex items-center hover:translate-x-[-4px] transition-transform bg-white px-4 py-2 rounded-xl shadow-sm border border-gray-100 w-fit uppercase tracking-widest">
        <span className="mr-2">←</span> Назад
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 w-full items-start">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1.5 h-full wb-gradient"></div>
            <div className="flex flex-col md:flex-row justify-between items-start mb-8">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-[9px] font-black text-purple-600 bg-purple-50 px-3 py-1 rounded-full uppercase tracking-widest border border-purple-100">{tender.category}</span>
                  <span className="text-[9px] font-black text-gray-400 bg-gray-50 px-3 py-1 rounded-full uppercase tracking-widest border border-gray-100">ID: {tender.id}</span>
                </div>
                <h1 className="text-xl font-black text-gray-900 leading-tight mb-3">{tender.title}</h1>
                <p className="text-[10px] text-gray-400 font-black uppercase tracking-widest">Метод: <span className="text-gray-900">{tender.method}</span></p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 p-6 bg-gray-50/50 rounded-xl border border-gray-100">
              <div>
                <p className="text-[9px] text-gray-400 mb-1.5 uppercase tracking-widest font-black">Макс. Бюджет</p>
                <p className="text-2xl font-black text-gray-900">{new Intl.NumberFormat('ru-RU', { style: 'currency', currency: tender.currency }).format(tender.budget)}</p>
              </div>
              <div className="md:border-l border-gray-100 md:pl-6">
                <p className="text-[9px] text-gray-400 mb-1.5 uppercase tracking-widest font-black">Окончание приема</p>
                <p className="text-2xl font-black text-gray-900">{tender.deadline}</p>
              </div>
            </div>

            <div className="mb-8">
              <h3 className="text-[10px] font-black text-gray-900 mb-4 uppercase tracking-[0.2em] opacity-30">Таймлайн процедуры</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {stages.map((stage, idx) => (
                  <div key={idx} className={`p-4 rounded-xl border transition-all ${stage.isActive ? 'bg-purple-50 border-purple-200' : stage.isCompleted ? 'bg-green-50/30 border-green-100' : 'bg-white border-gray-100'}`}>
                    <div className="flex justify-between items-start mb-1.5">
                       <span className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-tighter ${stage.isActive ? 'bg-purple-600 text-white' : stage.isCompleted ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'}`}>{idx + 1}</span>
                    </div>
                    <p className={`text-[11px] font-black uppercase mb-0.5 ${stage.isActive ? 'text-purple-700' : 'text-gray-900'}`}>{stage.title}</p>
                    <p className="text-[9px] text-gray-400 font-bold">{stage.date}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-8">
              <div>
                <h3 className="text-[10px] font-black text-gray-900 mb-3 uppercase tracking-[0.2em] opacity-30">Суть закупки</h3>
                <p className="text-gray-600 leading-relaxed text-[13px] font-medium whitespace-pre-wrap">{tender.description}</p>
              </div>
              
              <div>
                <h3 className="text-[10px] font-black text-gray-900 mb-3 uppercase tracking-[0.2em] opacity-30">Документация</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {tender.documents.map(doc => (
                    <div key={doc} className="flex items-center p-3 bg-white border border-gray-100 rounded-xl group cursor-pointer hover:border-purple-200 transition-all">
                      <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center mr-3 text-lg group-hover:bg-purple-50 transition-colors">📄</div>
                      <div className="flex-1">
                        <p className="text-[11px] font-black text-gray-800 uppercase tracking-tight line-clamp-1">{doc}</p>
                        <p className="text-[9px] text-gray-400 font-bold uppercase tracking-widest">PDF • 1.4 MB</p>
                      </div>
                      <div className="text-gray-200 group-hover:text-purple-600 ml-2">📥</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm relative overflow-hidden">
            <h3 className="text-base font-black text-gray-900 mb-6 uppercase tracking-wider">Участие</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-gray-50/50 rounded-xl border border-gray-100">
                <span className="text-[9px] text-gray-400 font-black uppercase tracking-widest">Конкуренция</span>
                <span className="font-black text-purple-600 text-xs">ВЫСОКАЯ</span>
              </div>
              <div className="flex justify-between items-center p-4 bg-gray-50/50 rounded-xl border border-gray-100">
                <span className="text-[9px] text-gray-400 font-black uppercase tracking-widest">Претендентов</span>
                <span className="font-black text-gray-900 text-xs">12 КОМПАНИЙ</span>
              </div>
              <div className="pt-4 space-y-2.5">
                <button 
                  onClick={() => setShowModal(true)}
                  className="w-full wb-gradient text-white font-black py-4 rounded-xl shadow-lg shadow-purple-50 hover:scale-[1.02] active:scale-[0.98] transition-all uppercase tracking-[0.15em] text-[11px]"
                >
                  Подать предложение
                </button>
                <button className="w-full bg-white border border-gray-200 text-gray-400 font-black py-4 rounded-xl hover:bg-gray-50 transition-all uppercase tracking-widest text-[10px]">
                  Добавить в избранное
                </button>
              </div>
              <p className="text-[8px] text-center text-gray-400 font-bold uppercase tracking-widest mt-2">Требуется наличие действующей ЭЦП</p>
            </div>
          </div>
          
          <div className="bg-gray-900 rounded-2xl p-8 text-white relative overflow-hidden">
            <h3 className="text-[10px] font-black mb-6 uppercase tracking-[0.2em] text-gray-500 border-b border-white/10 pb-3">Контактная группа</h3>
            <div className="space-y-5 relative z-10">
              <div className="flex items-center gap-4">
                <div className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center text-lg border border-white/5">👤</div>
                <div>
                  <p className="text-[13px] font-black">Иванов С.В.</p>
                  <p className="text-[8px] text-gray-500 font-black uppercase tracking-widest">Ведущий менеджер</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center text-lg border border-white/5">📧</div>
                <div>
                  <p className="text-[13px] font-black">sourcing@wb.ru</p>
                  <p className="text-[8px] text-gray-500 font-black uppercase tracking-widest">E-mail</p>
                </div>
              </div>
            </div>
            <button className="w-full mt-8 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[9px] font-black uppercase tracking-widest transition-all">
              Чат с организатором
            </button>
          </div>
          
          <div className="bg-purple-50 rounded-2xl p-6 border border-purple-100">
            <h4 className="text-[11px] font-black text-purple-900 uppercase tracking-widest mb-2">Частые вопросы</h4>
            <p className="text-[10px] text-purple-700 leading-relaxed font-medium mb-4">Узнайте, как правильно подготовить документы для участия в торгах Wildberries.</p>
            <button className="text-[9px] font-black text-purple-600 uppercase tracking-widest border-b border-purple-200">База знаний →</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TenderDetails;
