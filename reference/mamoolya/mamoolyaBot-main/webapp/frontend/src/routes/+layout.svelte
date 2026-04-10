<script>
  import { onMount } from 'svelte';
  import { api, getInitData } from '$lib/api.js';
  
  let user = null;
  let isLoading = true;
  let error = null;
  let hasTelegramData = false;
  
  onMount(async () => {
    console.log('[DEBUG] Инициализация приложения');
    console.log('[DEBUG] URL:', window.location.href);
    console.log('[DEBUG] Telegram WebApp доступен:', !!(window.Telegram && window.Telegram.WebApp));
    
    // Проверяем наличие данных от Telegram
    hasTelegramData = !!(
      (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) ||
      window.location.hash.includes('tgWebAppData') ||
      window.location.search.includes('tgWebAppData')
    );
    
    console.log('[DEBUG] Данные от Telegram найдены:', hasTelegramData);
    
    try {
      // Инициализация Telegram WebApp если доступен
      if (window.Telegram && window.Telegram.WebApp) {
        console.log('[DEBUG] Инициализация Telegram WebApp');
        window.Telegram.WebApp.ready();
      }
      
      // Пытаемся загрузить данные пользователя через API
      console.log('[DEBUG] Загрузка данных пользователя...');
      user = await api.getUser();
      console.log('[DEBUG] Данные пользователя получены:', user);
      
    } catch (err) {
      console.error('[DEBUG] Ошибка при загрузке данных:', err);
      console.error('[DEBUG] Детали ошибки:', err.message);
      
      // Если данные от Telegram есть, но возникла ошибка
      if (hasTelegramData) {
        console.log('[DEBUG] Данные от Telegram есть, пытаемся получить отладочную информацию');
        
        // Пытаемся получить информацию о состоянии сервера
        try {
          const healthInfo = await fetch(`${window.location.origin}/backend/api/health`, {
            headers: {
              'Content-Type': 'application/json'
            }
          }).then(res => res.json());
          
          console.log('[DEBUG] Информация о состоянии сервера:', healthInfo);
          
          // Если режим разработки выключен, но данные есть
          if (!healthInfo.development_mode && healthInfo.has_telegram_param) {
            error = 'Ошибка валидации данных Telegram. Попробуйте перезапустить приложение.';
          } else if (healthInfo.validation_error) {
            error = `Ошибка сервера: ${healthInfo.validation_error}`;
          } else {
            error = 'Ошибка подключения к серверу';
          }
        } catch (healthErr) {
          console.error('[DEBUG] Не удалось получить информацию о состоянии сервера:', healthErr);
          
          // Пытаемся получить отладочную информацию (старый способ)
          try {
            const debugInfo = await api.getDebugInfo();
            console.log('[DEBUG] Отладочная информация с сервера:', debugInfo);
            
            // Если валидация прошла успешно, но пользователь fallback - создаем минимальные данные
            if (debugInfo.parsed_user) {
              user = {
                id: debugInfo.parsed_user.id,
                first_name: debugInfo.parsed_user.first_name || 'Пользователь',
                username: debugInfo.parsed_user.username || '',
                avatar_url: `https://krksksoc-maman.up.railway.app/userpics/${debugInfo.parsed_user.id}.jpg`
              };
              console.log('[DEBUG] Созданы данные пользователя из отладочной информации:', user);
            } else {
              error = 'Не удалось получить данные пользователя';
            }
          } catch (debugErr) {
            console.error('[DEBUG] Не удалось получить отладочную информацию:', debugErr);
            
            // Проверим, является ли ошибка связанной с сетью
            if (err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
              error = 'Ошибка сети. Проверьте подключение к интернету.';
            } else if (err.message.includes('401')) {
              error = 'Данные авторизации недействительны. Перезапустите приложение из Telegram.';
            } else {
              error = 'Ошибка сервера. Попробуйте позже.';
            }
          }
        }
      } else {
        // Если данных от Telegram нет, показываем стандартное сообщение
        error = 'Приложение должно быть запущено из Telegram';
      }
    }
    
    isLoading = false;
  });
</script>

<svelte:head>
  <title>WebApp Мамули</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</svelte:head>

<div class="app">
  {#if isLoading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Загрузка...</p>
    </div>
  {:else if error}
    <div class="error-screen">
      <h2>⚠️ {error}</h2>
      {#if !hasTelegramData}
        <div class="error-details">
          <strong>Как запустить приложение:</strong><br>
          • Откройте Telegram<br>
          • Найдите бота @mamoolyabot<br>
          • Нажмите на кнопку "Открыть приложение"
        </div>
      {:else}
        <div class="error-details">
          <p>Попробуйте:</p>
          <ul>
            <li>Обновить страницу</li>
            <li>Перезапустить приложение из Telegram</li>
            <li>Проверить подключение к интернету</li>
          </ul>
        </div>
      {/if}
    </div>
  {:else if user}
    <header class="header">
      <div class="user-info">
        <img 
          src={user.avatar_url} 
          alt="Аватар" 
          class="avatar"
          on:error={(e) => { e.target.src = 'https://telegram.org/img/t_logo.png'; }}
        />
        <div class="user-details">
          <div class="name">{user.first_name}</div>
          {#if user.username}
            <div class="username">@{user.username}</div>
          {/if}
        </div>
      </div>
    </header>
    
    <main class="main">
      <slot />
    </main>
  {/if}
</div>

<style>
  :global(body) {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f4f6fb;
    margin: 0;
    padding: 0;
  }
  
  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    color: #666;
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3b5998;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .error-screen {
    padding: 40px 20px;
    text-align: center;
    max-width: 420px;
    margin: 0 auto;
  }
  
  .error-screen h2 {
    color: #d17a00;
    margin-bottom: 16px;
    font-size: 18px;
  }
  
  .error-screen p {
    color: #666;
    margin-bottom: 20px;
  }
  
  .error-details {
    background: #fff3e0;
    padding: 16px;
    border-radius: 8px;
    color: #d17a00;
    text-align: left;
    border: 1px solid #ffcc02;
  }
  
  .error-details ul {
    margin: 8px 0;
    padding-left: 20px;
  }
  
  .error-details li {
    margin: 4px 0;
    color: #666;
  }
  
  .header {
    background: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    padding: 16px 20px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  
  .user-info {
    display: flex;
    align-items: center;
    max-width: 420px;
    margin: 0 auto;
  }
  
  .avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    margin-right: 12px;
    border: 2px solid #e0e0e0;
    object-fit: cover;
  }
  
  .user-details {
    flex: 1;
  }
  
  .name {
    font-weight: 600;
    font-size: 16px;
    color: #333;
    margin-bottom: 2px;
  }
  
  .username {
    font-size: 14px;
    color: #666;
  }
  
  .main {
    flex: 1;
    padding: 20px;
  }
  
  :global(.container) {
    max-width: 420px;
    margin: 0 auto;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    padding: 24px;
  }
</style>
