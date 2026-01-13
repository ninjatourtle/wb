
import { GoogleGenAI, Type } from "@google/genai";
import { Tender, AIAnalysisResult } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });

export const analyzeTender = async (tender: Tender): Promise<AIAnalysisResult> => {
  const prompt = `
    Проанализируй следующий тендер компании Wildberries и дай рекомендации для поставщика на РУССКОМ ЯЗЫКЕ:
    Название: ${tender.title}
    Категория: ${tender.category}
    Описание: ${tender.description}
    Бюджет: ${tender.budget} ${tender.currency}
    
    Ответь в формате JSON.
  `;

  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          summary: { type: Type.STRING, description: "Краткий анализ тендера" },
          keyRequirements: { 
            type: Type.ARRAY,
            items: { type: Type.STRING },
            description: "Ключевые требования к поставщику"
          },
          riskAssessment: { type: Type.STRING, description: "Оценка рисков" },
          suggestedBidRange: { type: Type.STRING, description: "Рекомендуемый диапазон цен" }
        },
        required: ["summary", "keyRequirements", "riskAssessment", "suggestedBidRange"]
      }
    }
  });

  return JSON.parse(response.text || '{}');
};

export const chatWithAssistant = async (message: string, context: Tender) => {
  const prompt = `
    Ты — интеллектуальный помощник тендерной платформы Wildberries. 
    Помогаешь поставщикам понять требования закупки.
    Контекст закупки: ${context.title} (${context.description})
    Вопрос пользователя: ${message}
    Отвечай вежливо, профессионально и на РУССКОМ ЯЗЫКЕ.
  `;

  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
  });

  return response.text;
};
