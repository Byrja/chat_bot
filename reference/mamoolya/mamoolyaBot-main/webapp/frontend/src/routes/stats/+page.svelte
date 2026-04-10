<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  
  let stats = null;
  let error = '';
  let isLoading = true;
  
  onMount(async () => {
    try {
      stats = await api.getUserStats();
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  });
  
  function goBack() {
    goto('/');
  }
</script>

<div class="container">
  <h2>📊 Моя статистика</h2>
  
  {#if isLoading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Загрузка статистики...</p>
    </div>
  {:else if error}
    <div class="error">
      <div class="error-icon">❌</div>
      <div class="error-message">
        <strong>Ошибка загрузки</strong><br>
        {error}
      </div>
    </div>
  {:else if stats}
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📝</div>
        <div class="stat-content">
          <div class="stat-value">{stats.user_anon_count}</div>
          <div class="stat-label">Анонимных сообщений</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">🗳️</div>
        <div class="stat-content">
          <div class="stat-value">{stats.user_votes_count}</div>
          <div class="stat-label">Моих голосов</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">👥</div>
        <div class="stat-content">
          <div class="stat-value">{stats.votes_about_user}</div>
          <div class="stat-label">Голосов обо мне</div>
        </div>
      </div>
    </div>
    
    <div class="ratings-section">
      <h3>Как меня оценили</h3>
      
      {#if stats.votes_breakdown && Object.keys(stats.votes_breakdown).length > 0}
        <div class="ratings-grid">
          <div class="rating-card friends">
            <div class="rating-icon">👥</div>
            <div class="rating-content">
              <div class="rating-value">{stats.votes_breakdown.friend || 0}</div>
              <div class="rating-label">Друзья</div>
            </div>
          </div>
          
          <div class="rating-card neutral">
            <div class="rating-icon">😐</div>
            <div class="rating-content">
              <div class="rating-value">{stats.votes_breakdown.neutral || 0}</div>
              <div class="rating-label">Нейтрально</div>
            </div>
          </div>
          
          <div class="rating-card foes">
            <div class="rating-icon">👿</div>
            <div class="rating-content">
              <div class="rating-value">{stats.votes_breakdown.foe || 0}</div>
              <div class="rating-label">Козлы</div>
            </div>
          </div>
        </div>
      {:else}
        <div class="no-ratings">
          <div class="no-ratings-icon">🤷‍♂️</div>
          <p>Пока нет оценок</p>
        </div>
      {/if}
    </div>
  {/if}
  
  <div class="buttons">
    <button on:click={goBack}>🏠 На главную</button>
  </div>
</div>

<style>
  h2 {
    text-align: center;
    margin-top: 0;
    color: #333;
    margin-bottom: 32px;
  }
  
  h3 {
    color: #333;
    margin-bottom: 16px;
    font-size: 18px;
  }
  
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 0;
    color: #666;
  }
  
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #3b5998;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .error {
    display: flex;
    align-items: center;
    padding: 20px;
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 12px;
    margin-bottom: 24px;
  }
  
  .error-icon {
    font-size: 24px;
    margin-right: 16px;
  }
  
  .error-message {
    color: #721c24;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }
  
  .stat-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  }
  
  .stat-icon {
    font-size: 28px;
    margin-right: 16px;
  }
  
  .stat-content {
    flex: 1;
  }
  
  .stat-value {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 4px;
  }
  
  .stat-label {
    font-size: 12px;
    opacity: 0.9;
  }
  
  .ratings-section {
    margin-bottom: 32px;
  }
  
  .ratings-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  
  .rating-card {
    padding: 16px;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  
  .rating-card.friends {
    background: #d4edda;
    border: 1px solid #c3e6cb;
  }
  
  .rating-card.neutral {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
  }
  
  .rating-card.foes {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
  }
  
  .rating-icon {
    font-size: 24px;
    margin-bottom: 8px;
  }
  
  .rating-value {
    font-size: 20px;
    font-weight: 700;
    color: #333;
    margin-bottom: 4px;
  }
  
  .rating-label {
    font-size: 12px;
    color: #666;
  }
  
  .no-ratings {
    text-align: center;
    padding: 40px 0;
    color: #666;
  }
  
  .no-ratings-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }
  
  .buttons {
    text-align: center;
  }
  
  button {
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
  
  button:hover {
    background: #2d4373;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 89, 152, 0.4);
  }
</style> 