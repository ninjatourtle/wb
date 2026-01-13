
import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

const data = [
  { name: 'Янв', value: 4000 },
  { name: 'Фев', value: 3000 },
  { name: 'Мар', value: 2000 },
  { name: 'Апр', value: 2780 },
  { name: 'Май', value: 1890 },
  { name: 'Июн', value: 2390 },
];

const Dashboard: React.FC<{ isProfile?: boolean }> = ({ isProfile }) => {
  const [activeTab, setActiveTab] = useState(isProfile ? 'settings' : 'stats');

  return (
    <div className="w-full px-6 py-8">
      <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h2 className="text-2xl font-black text-gray-900 tracking-tight">{isProfile ? 'Профиль компании' : 'Аналитический реестр'}</h2>
          <p className="text-xs text-gray-400 font-medium mt-1">
            {isProfile ? 'Управление аккаунтом организации и безопасность' : 'Статистические данные по закупкам группы WB'}
          </p>
        </div>
        
        {isProfile && (
          <div className="flex bg-white p-1 rounded-xl border border-gray-100 shadow-sm">
            <button 
              onClick={() => setActiveTab('stats')}
              className={`px-5 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'stats' ? 'bg-purple-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-600'}`}
            >
              Активность
            </button>
            <button 
              onClick={() => setActiveTab('settings')}
              className={`px-5 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'settings' ? 'bg-purple-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-600'}`}
            >
              Настройки
            </button>
            <button 
              onClick={() => setActiveTab('security')}
              className={`px-5 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'security' ? 'bg-purple-600 text-white shadow-md' : 'text-gray-400 hover:text-gray-600'}`}
            >
              Безопасность
            </button>
          </div>
        )}
      </div>

      {activeTab === 'stats' && (
        <div className="space-y-8 animate-in fade-in duration-300">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Всего заявок', value: '8', change: '+2', color: 'text-purple-600' },
              { label: 'Побед', value: '3', change: '37%', color: 'text-green-600' },
              { label: 'Контракты', value: '45.2М ₽', change: '+12%', color: 'text-gray-900' },
              { label: 'Рейтинг', value: '4.8', change: 'TOP', color: 'text-orange-500' },
            ].map((stat, i) => (
              <div key={i} className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
                <p className="text-[9px] text-gray-400 font-black uppercase tracking-widest mb-1.5">{stat.label}</p>
                <p className={`text-xl font-black ${stat.color}`}>{stat.value}</p>
                <div className="mt-3 flex items-center gap-1.5">
                  <span className="text-[9px] font-black text-green-600">{stat.change}</span>
                  <span className="text-[8px] text-gray-300 font-bold uppercase">vs прошлый мес</span>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
              <h3 className="text-[10px] font-black text-gray-400 mb-6 uppercase tracking-widest">Динамика оборота</h3>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data}>
                    <defs>
                      <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#cb11ab" stopOpacity={0.1}/>
                        <stop offset="95%" stopColor="#cb11ab" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fontSize: 9, fontWeight: 700, fill: '#9ca3af'}} />
                    <YAxis axisLine={false} tickLine={false} tick={{fontSize: 9, fontWeight: 700, fill: '#9ca3af'}} />
                    <Tooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', fontSize: '10px'}} />
                    <Area type="monotone" dataKey="value" stroke="#cb11ab" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
              <h3 className="text-[10px] font-black text-gray-400 mb-6 uppercase tracking-widest">Участие по категориям</h3>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fontSize: 9, fontWeight: 700, fill: '#9ca3af'}} />
                    <YAxis axisLine={false} tickLine={false} tick={{fontSize: 9, fontWeight: 700, fill: '#9ca3af'}} />
                    <Tooltip cursor={{fill: '#f9fafb'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', fontSize: '10px'}} />
                    <Bar dataKey="value" fill="#8d23d2" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-in slide-in-from-right-2 duration-300">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm">
              <h3 className="text-[10px] font-black text-gray-900 mb-6 uppercase tracking-[0.2em] opacity-30">Общие данные</h3>
              <form className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[9px] font-black text-gray-400 uppercase tracking-widest mb-1.5">Наименование ЮЛ</label>
                    <input type="text" defaultValue="ООО ТЕХНОТОРГ" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 font-bold text-xs bg-gray-50/20 outline-none focus:border-purple-600 transition-colors" />
                  </div>
                  <div>
                    <label className="block text-[9px] font-black text-gray-400 uppercase tracking-widest mb-1.5">ИНН / ОГРН</label>
                    <input type="text" defaultValue="7712345678 / 112771234" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 font-bold text-xs bg-gray-50/20 outline-none focus:border-purple-600 transition-colors" />
                  </div>
                </div>
                <div>
                  <label className="block text-[9px] font-black text-gray-400 uppercase tracking-widest mb-1.5">Электронная почта для уведомлений</label>
                  <input type="email" defaultValue="office@technotorg.ru" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 font-bold text-xs bg-gray-50/20 outline-none focus:border-purple-600 transition-colors" />
                </div>
                <div>
                  <label className="block text-[9px] font-black text-gray-400 uppercase tracking-widest mb-1.5">Юридический адрес</label>
                  <input type="text" defaultValue="123456, г. Москва, ул. Примерная, д. 10" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 font-bold text-xs bg-gray-50/20 outline-none focus:border-purple-600 transition-colors" />
                </div>
                <div className="pt-4 border-t border-gray-100 flex justify-end">
                  <button type="button" className="wb-gradient text-white px-8 py-3 rounded-xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-purple-50">Сохранить</button>
                </div>
              </form>
            </div>
            
            <div className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm">
              <h3 className="text-[10px] font-black text-gray-900 mb-6 uppercase tracking-[0.2em] opacity-30">Настройки уведомлений</h3>
              <div className="space-y-4">
                {[
                  { label: 'Новые тендеры по моим категориям', active: true },
                  { label: 'Изменение статуса моих заявок', active: true },
                  { label: 'Ответы от организаторов в чате', active: false },
                  { label: 'Новости и обновления регламента', active: true },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between items-center py-2 border-b border-gray-50 last:border-0">
                    <span className="text-[11px] font-bold text-gray-600">{item.label}</span>
                    <div className={`w-10 h-5 rounded-full relative cursor-pointer transition-colors ${item.active ? 'bg-purple-600' : 'bg-gray-200'}`}>
                      <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 transition-all ${item.active ? 'left-5.5' : 'left-0.5'}`}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          
          <div className="space-y-6">
            <div className="bg-gray-900 rounded-2xl p-8 text-white shadow-xl">
               <h3 className="text-[10px] font-black mb-6 uppercase tracking-widest text-gray-500">Банковские данные</h3>
               <div className="space-y-4">
                  <div>
                    <p className="text-[8px] text-gray-500 font-black uppercase tracking-widest mb-1">Р/С</p>
                    <p className="text-[11px] font-bold font-mono">40702810400000001234</p>
                  </div>
                  <div>
                    <p className="text-[8px] text-gray-500 font-black uppercase tracking-widest mb-1">БИК</p>
                    <p className="text-[11px] font-bold font-mono">044525225</p>
                  </div>
                  <div>
                    <p className="text-[8px] text-gray-500 font-black uppercase tracking-widest mb-1">Банк</p>
                    <p className="text-[10px] font-black uppercase text-gray-300">ПАО СБЕРБАНК</p>
                  </div>
               </div>
               <button className="w-full mt-8 py-3 bg-white/5 border border-white/10 rounded-xl text-[9px] font-black uppercase tracking-widest hover:bg-white/10 transition-all">Редактировать</button>
            </div>
            
            <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm text-center">
               <div className="w-16 h-16 bg-purple-50 rounded-full flex items-center justify-center mx-auto mb-3 text-2xl">🛡️</div>
               <h4 className="text-[11px] font-black text-gray-900 mb-2 uppercase">Цифровая подпись</h4>
               <p className="text-[10px] text-gray-400 leading-relaxed font-medium mb-4">Активен до: 12.12.2024</p>
               <button className="text-[9px] font-black text-purple-600 uppercase tracking-widest">Продлить доступ →</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'security' && (
        <div className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm animate-in zoom-in-95 duration-300">
           <h3 className="text-[10px] font-black text-gray-900 mb-8 uppercase tracking-[0.2em] opacity-30">Безопасность аккаунта</h3>
           <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
              <div className="space-y-6">
                 <div>
                    <h4 className="text-[11px] font-black text-gray-800 uppercase mb-3">Двухфакторная аутентификация</h4>
                    <p className="text-[11px] text-gray-500 mb-4">Дополнительный уровень защиты вашего аккаунта при входе.</p>
                    <button className="text-[10px] font-black text-white bg-gray-900 px-6 py-2.5 rounded-lg uppercase tracking-widest">Настроить 2FA</button>
                 </div>
                 <div className="pt-6 border-t border-gray-50">
                    <h4 className="text-[11px] font-black text-gray-800 uppercase mb-3">Смена пароля</h4>
                    <p className="text-[11px] text-gray-500 mb-4">Рекомендуется менять пароль не реже одного раза в 90 дней.</p>
                    <button className="text-[10px] font-black text-purple-600 border border-purple-200 px-6 py-2.5 rounded-lg uppercase tracking-widest hover:bg-purple-50">Изменить пароль</button>
                 </div>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl border border-gray-100">
                 <h4 className="text-[11px] font-black text-gray-800 uppercase mb-4">Последние сессии</h4>
                 <div className="space-y-3">
                    {[
                       { device: 'Chrome / Windows', ip: '192.168.1.1', date: 'Сегодня, 14:20' },
                       { device: 'Mobile App / iOS', ip: '94.25.160.12', date: 'Вчера, 09:15' },
                       { device: 'Firefox / MacOS', ip: '176.59.32.44', date: '15.05.2024' },
                    ].map((session, i) => (
                       <div key={i} className="flex justify-between items-center text-[10px] border-b border-gray-200/50 pb-2 last:border-0">
                          <div>
                             <p className="font-bold text-gray-700">{session.device}</p>
                             <p className="text-gray-400">{session.ip}</p>
                          </div>
                          <span className="text-gray-400 font-medium">{session.date}</span>
                       </div>
                    ))}
                 </div>
                 <button className="w-full mt-6 text-[9px] font-black text-red-500 uppercase tracking-widest border border-red-100 py-2 rounded-lg hover:bg-red-50">Завершить все сеансы</button>
              </div>
           </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
