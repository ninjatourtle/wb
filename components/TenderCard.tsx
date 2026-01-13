
import React from 'react';
import { Tender, TenderStatus } from '../types';

interface TenderCardProps {
  tender: Tender;
  onClick: (tender: Tender) => void;
}

const TenderCard: React.FC<TenderCardProps> = ({ tender, onClick }) => {
  const getStatusColor = (status: TenderStatus) => {
    switch (status) {
      case TenderStatus.OPEN: return 'bg-green-100 text-green-700';
      case TenderStatus.REVIEW: return 'bg-yellow-100 text-yellow-700';
      case TenderStatus.CLOSED: return 'bg-red-100 text-red-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div 
      onClick={() => onClick(tender)}
      className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-lg transition-all cursor-pointer group"
    >
      <div className="flex justify-between items-start mb-4">
        <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${getStatusColor(tender.status)}`}>
          {tender.status}
        </span>
        <span className="text-sm font-semibold text-gray-400">{tender.id}</span>
      </div>
      <h3 className="text-lg font-bold text-gray-900 mb-2 group-hover:text-purple-700 transition-colors h-14 overflow-hidden">
        {tender.title}
      </h3>
      <p className="text-sm text-gray-500 line-clamp-2 mb-4">
        {tender.description}
      </p>
      <div className="flex items-center justify-between mt-auto">
        <div className="flex flex-col">
          <span className="text-xs text-gray-400 uppercase">Бюджет</span>
          <span className="text-md font-bold text-gray-900">
            {new Intl.NumberFormat('ru-RU', { style: 'currency', currency: tender.currency, maximumFractionDigits: 0 }).format(tender.budget)}
          </span>
        </div>
        <div className="flex flex-col text-right">
          <span className="text-xs text-gray-400 uppercase">До</span>
          <span className="text-sm font-semibold text-gray-700">{tender.deadline}</span>
        </div>
      </div>
    </div>
  );
};

export default TenderCard;
