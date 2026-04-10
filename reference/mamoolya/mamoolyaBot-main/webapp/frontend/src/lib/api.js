//const API_BASE = location?.hostname === 'localhost' || location?.hostname === '127.0.0.1' ? 'http://127.0.0.1:5001' : 'https://krksksoc-maman.up.railway.app/backend';
const API_BASE = 'https://krksksoc-maman.up.railway.app/';

// Получение initData для отправки в заголовках
export function getInitData() {
  if (typeof window !== 'undefined' && window.location) {
    try {
      // Пытаемся получить данные из Telegram WebApp
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        console.log('[DEBUG] Получены данные из Telegram WebApp:', window.Telegram.WebApp.initData);
        return window.Telegram.WebApp.initData;
      }
      
      // Fallback: пытаемся получить данные из URL хэша (для режима разработки)
      if (window.location.hash) {
        const hashParams = new URLSearchParams(window.location.hash.slice(1));
        const tgWebAppData = hashParams.get('tgWebAppData');
        if (tgWebAppData) {
          console.log('[DEBUG] Получены данные из URL хэша:', tgWebAppData);
          try {
            return decodeURIComponent(tgWebAppData);
          } catch (decodeError) {
            console.error('[DEBUG] Ошибка декодирования данных из хэша:', decodeError);
            return null;
          }
        }
      }
      
      // Fallback: пытаемся получить данные из URL параметров
      if (window.location.search) {
        const urlParams = new URLSearchParams(window.location.search);
        const tgWebAppData = urlParams.get('tgWebAppData');
        if (tgWebAppData) {
          console.log('[DEBUG] Получены данные из URL параметров:', tgWebAppData);
          try {
            return decodeURIComponent(tgWebAppData);
          } catch (decodeError) {
            console.error('[DEBUG] Ошибка декодирования данных из параметров:', decodeError);
            return null;
          }
        }
      }
      
      console.log('[DEBUG] Данные Telegram WebApp не найдены');
    } catch (error) {
      console.error('[DEBUG] Общая ошибка при получении initData:', error);
    }
  }
  return null;
}

// Базовая функция для API запросов с автоматической авторизацией
export async function apiRequest(endpoint, options = {}) {
  const initData = getInitData();
  console.log('[API] Отправляем запрос:', endpoint);
  console.log('[API] InitData для URL:', initData ? initData.substring(0, 100) + '...' : 'отсутствует');
  
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  // Добавляем Telegram initData как URL параметр
  let finalEndpoint = endpoint;
  if (initData) {
    const separator = endpoint.includes('?') ? '&' : '?';
    try {
      finalEndpoint = `${endpoint}${separator}tgWebAppData=${encodeURIComponent(initData)}`;
      console.log('[API] Добавлен URL параметр tgWebAppData');
    } catch (encodeError) {
      console.error('[API] Ошибка кодирования URL параметра:', encodeError);
    }
  } else {
    console.log('[API] Данные initData отсутствуют, параметр не добавлен');
  }

  console.log('[API] Заголовки запроса:', Object.keys(headers));
  console.log('[API] Итоговый URL:', `${API_BASE}${finalEndpoint}`);

  try {
    const response = await fetch(`${API_BASE}${finalEndpoint}`, {
      ...options,
      headers,
    });

    console.log('[API] Статус ответа:', response.status);

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch (jsonError) {
        console.error('[API] Ошибка парсинга JSON ошибки:', jsonError);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      console.error('[API] Ошибка ответа:', errorData);
      throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    let result;
    try {
      result = await response.json();
    } catch (jsonError) {
      console.error('[API] Ошибка парсинга JSON ответа:', jsonError);
      throw new Error('Ошибка обработки ответа сервера');
    }
    
    console.log('[API] Успешный ответ:', result);
    return result;
  } catch (fetchError) {
    console.error('[API] Ошибка fetch:', fetchError);
    throw fetchError;
  }
}

// Специфичные API методы
export const api = {
  // Получение данных пользователя
  getUser: () => apiRequest('/api/user'),
  
  // Отправка анонимного сообщения
  sendAnon: (message) => apiRequest('/api/anon', {
    method: 'POST',
    body: JSON.stringify({ message }),
  }),
  
  // Получение статистики
  getStats: () => apiRequest('/api/stats'),
  getUserStats: () => apiRequest('/api/user_stats'),
  
  // Друзья и козлы
  getFriendsAnketa: () => apiRequest('/api/friends/anketa'),
  voteFriend: (target_user_id, relation) => apiRequest('/api/friends/vote', {
    method: 'POST',
    body: JSON.stringify({ target_user_id, relation }),
  }),
  getMyLists: () => apiRequest('/api/friends/my_lists'),
  getWhoAddedMe: () => apiRequest('/api/friends/who_added_me'),
  
  // Цитаты
  getQuotes: () => apiRequest('/api/quotes'),
  
  // Зодиак
  getZodiac: () => apiRequest('/api/zodiac'),
  setZodiac: (zodiac_sign) => apiRequest('/api/zodiac', {
    method: 'POST',
    body: JSON.stringify({ zodiac_sign }),
  }),
  
  // Отладка (только в режиме разработки)
  getDebugInfo: () => apiRequest('/api/debug'),
  getTestUserSimple: () => apiRequest('/api/test_user_simple'),
}; 
