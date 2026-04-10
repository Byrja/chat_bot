<script>
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  
  function navigateToAnon() {
    goto('/anon');
  }
  
  function navigateToStats() {
    goto('/stats');
  }
  
  function navigateToFriends() {
    goto('/friends');
  }
  
  function navigateToQuotes() {
    goto('/quotes');
  }
  
  function navigateToZodiac() {
    goto('/zodiac');
  }
  
  function navigateToDebug() {
    goto('/debug');
  }
  
  // Проверяем, находимся ли мы в режиме разработки
  $: isDevelopment = browser && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
</script>

<div class="container">
  <h1>🤖 WebApp Мамули </h1>
  
  <div class="welcome">
    Добро пожаловать в WebApp Мамули! Здесь вы можете:
  </div>
  
  <div class="buttons">
    <button on:click={navigateToAnon}>
      📝 Анонимное признание
    </button>
    <button on:click={navigateToStats}>
      📊 Моя статистика
    </button>
    <button on:click={navigateToFriends}>
      👥 Друзья и козлы
    </button>
    <button on:click={navigateToZodiac}>
      🔮 Мой знак зодиака
    </button>
    <button on:click={navigateToQuotes}>
      📚 Цитатник
    </button>
  </div>
  
  <div class="features">
    <div class="feature">
      <div class="feature-icon">📝</div>
      <div class="feature-text">
        <strong>Анонимные признания</strong><br>
        Отправляйте анонимные сообщения мамуле 🤐
      </div>
    </div>
    
    <div class="feature">
      <div class="feature-icon">📊</div>
      <div class="feature-text">
        <strong>Статистика</strong><br>
        Просматривайте свою активность и рейтинги
      </div>
    </div>
    
    <div class="feature">
      <div class="feature-icon">👥</div>
      <div class="feature-text">
        <strong>Друзья и козлы</strong><br>
        Оценивайте других участников сообщества
      </div>
    </div>
    
    <div class="feature">
      <div class="feature-icon">🔮</div>
      <div class="feature-text">
        <strong>Знак зодиака</strong><br>
        Выберите свой знак для персонального гороскопа
      </div>
    </div>
    
    <div class="feature">
      <div class="feature-icon">📚</div>
      <div class="feature-text">
        <strong>Цитатник</strong><br>
        Просматривайте "золотые фразы" участников чата
      </div>
    </div>
  </div>
  
  {#if isDevelopment}
    <div class="debug-section">
      <h3>🔧 Режим разработки</h3>
      <button class="debug-button" on:click={navigateToDebug}>
        🐞 Отладочная информация
      </button>
    </div>
  {/if}
</div>

<style>
  h1 {
    text-align: center;
    margin-top: 0;
    color: #333;
    margin-bottom: 24px;
  }
  
  .welcome {
    text-align: center;
    color: #666;
    margin-bottom: 24px;
    font-size: 16px;
  }
  
  .buttons {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 32px;
  }
  
  .buttons button {
    padding: 16px 20px;
    border: none;
    border-radius: 12px;
    background: #3b5998;
    color: white;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(59, 89, 152, 0.3);
  }
  
  .buttons button:hover {
    background: #2d4373;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 89, 152, 0.4);
  }
  
  .debug-button {
    background: #ffc107 !important;
    color: #212529 !important;
    font-weight: 600 !important;
  }
  
  .debug-button:hover {
    background: #e0a800 !important;
  }
  
  .features {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .feature {
    display: flex;
    align-items: center;
    padding: 16px;
    background: #f8f9fa;
    border-radius: 12px;
    border: 1px solid #e9ecef;
  }
  
  .feature-icon {
    font-size: 28px;
    margin-right: 16px;
    flex-shrink: 0;
  }
  
  .feature-text {
    flex: 1;
    color: #495057;
  }
  
  .feature-text strong {
    color: #333;
  }
  
  .debug-section {
    margin-top: 32px;
    padding-top: 20px;
    border-top: 1px solid #e9ecef;
  }
  
  .debug-section h3 {
    margin-top: 0;
    color: #333;
    text-align: center;
  }
</style>