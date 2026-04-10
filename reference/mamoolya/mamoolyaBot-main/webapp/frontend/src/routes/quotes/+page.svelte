<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  
  let quotes = [];
  let loading = false;
  let error = null;
  
  // Функция для получения цитат
  async function loadQuotes() {
    try {
      loading = true;
      error = null;
      
      const response = await api.getQuotes();
      quotes = response.quotes || [];
    } catch (err) {
      console.error('Ошибка при загрузке цитат:', err);
      error = err.message || 'Не удалось загрузить цитаты';
    } finally {
      loading = false;
    }
  }
  
  // Загружаем цитаты при монтировании компонента
  onMount(() => {
    loadQuotes();
  });
  
  // Функция для обновления цитат
  function refreshQuotes() {
    loadQuotes();
  }
  
  // Функция для перехода на главную страницу
  function goBack() {
    goto('/');
  }
</script>

<div class="quotes-container">
  <div class="header">
    <h1>📚 Цитатник</h1>
    <button class="refresh-btn" on:click={refreshQuotes} disabled={loading}>
      {#if loading}
        🔄 Загрузка...
      {:else}
        🔄 Обновить
      {/if}
    </button>
  </div>
  
  {#if error}
    <div class="error-message">
      ❌ {error}
    </div>
  {/if}
  
  {#if loading && quotes.length === 0}
    <div class="loading-message">
      🔄 Загрузка цитат...
    </div>
  {/if}
  
  {#if quotes.length > 0}
    <div class="quotes-list">
      {#each quotes as quote (quote.id)}
        <div class="quote-card">
          <div class="quote-content">
            "{quote.message}"
          </div>
          <div class="quote-author">
            — {quote.username}
          </div>
          <div class="quote-meta">
            <span class="quote-date">
              {new Date(quote.timestamp).toLocaleDateString('ru-RU')}
            </span>
            <a href={quote.message_link} target="_blank" rel="noopener noreferrer" class="quote-link">
              🔗 Оригинал
            </a>
          </div>
        </div>
      {/each}
    </div>
  {:else if !loading && quotes.length === 0 && !error}
    <div class="no-quotes">
      📝 Пока нет сохраненных цитат.<br>
      Используйте команду /quote в чате, чтобы сохранить цитату.
    </div>
  {/if}
  
  <div class="buttons">
    <button on:click={goBack}>🏠 На главную</button>
  </div>
</div>

<style>
  .quotes-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    flex-wrap: wrap;
    gap: 15px;
  }
  
  h1 {
    margin: 0;
    color: #333;
    font-size: 28px;
  }
  
  .refresh-btn {
    padding: 10px 20px;
    background: #3b5998;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    font-weight: 500;
    transition: all 0.3s ease;
    box-shadow: 0 2px 6px rgba(59, 89, 152, 0.3);
  }
  
  .refresh-btn:hover:not(:disabled) {
    background: #2d4373;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 89, 152, 0.4);
  }
  
  .refresh-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  
  .error-message {
    background: #f8d7da;
    color: #721c24;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid #f5c6cb;
    margin-bottom: 20px;
  }
  
  .loading-message {
    text-align: center;
    padding: 30px;
    font-size: 18px;
    color: #666;
  }
  
  .quotes-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  
  .quote-card {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  
  .quote-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  }
  
  .quote-content {
    font-size: 18px;
    line-height: 1.6;
    color: #333;
    margin-bottom: 15px;
    font-style: italic;
  }
  
  .quote-author {
    font-weight: 600;
    color: #3b5998;
    margin-bottom: 10px;
    font-size: 16px;
  }
  
  .quote-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
    color: #6c757d;
  }
  
  .quote-date {
    font-weight: 500;
  }
  
  .quote-link {
    color: #3b5998;
    text-decoration: none;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 5px;
    transition: color 0.2s ease;
  }
  
  .quote-link:hover {
    color: #2d4373;
    text-decoration: underline;
  }
  
  .no-quotes {
    text-align: center;
    padding: 40px 20px;
    color: #6c757d;
    font-size: 18px;
    line-height: 1.6;
  }
  
  .buttons {
    text-align: center;
    margin-top: 30px;
  }
  
  .buttons button {
    padding: 16px 24px;
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
  
  @media (max-width: 768px) {
    .quotes-container {
      padding: 15px;
    }
    
    .header {
      flex-direction: column;
      align-items: stretch;
    }
    
    h1 {
      font-size: 24px;
      text-align: center;
    }
    
    .refresh-btn {
      align-self: center;
    }
    
    .quote-content {
      font-size: 16px;
    }
  }
</style>