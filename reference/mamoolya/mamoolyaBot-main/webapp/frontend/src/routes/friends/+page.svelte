<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  
  let anketaData = null;
  let anketaError = '';
  let lists = null;
  let listsError = '';
  let isAnketaLoading = true;
  let isVoting = false;
  let showingLists = false;
  let showingWhoAddedMe = false;
  
  onMount(async () => {
    await loadAnketa();
  });
  
  async function loadAnketa() {
    isAnketaLoading = true;
    anketaError = '';
    
    try {
      const data = await api.getFriendsAnketa();
      
      if (data.message) {
        anketaError = data.message;
      } else {
        anketaData = data.user;
      }
    } catch (error) {
      anketaError = error.message;
    } finally {
      isAnketaLoading = false;
    }
  }
  
  async function vote(relation) {
    if (!anketaData) return;
    
    isVoting = true;
    
    try {
      await api.voteFriend(anketaData.user_id, relation);
      // Перезагружаем анкету после голосования
      anketaData = null;
      await loadAnketa();
    } catch (error) {
      alert('Ошибка: ' + error.message);
    } finally {
      isVoting = false;
    }
  }
  
  async function showMyLists() {
    showingLists = true;
    showingWhoAddedMe = false;
    lists = null;
    listsError = '';
    
    try {
      lists = await api.getMyLists();
    } catch (error) {
      listsError = error.message;
    }
  }
  
  async function showWhoAddedMe() {
    showingWhoAddedMe = true;
    showingLists = false;
    lists = null;
    listsError = '';
    
    try {
      lists = await api.getWhoAddedMe();
    } catch (error) {
      listsError = error.message;
    }
  }
  
  function goBack() {
    goto('/');
  }
  
  function getUsersNames(users) {
    if (!users || users.length === 0) return 'нет';
    return users.map(u => u.username ? '@' + u.username : (u.first_name || 'Неизвестно')).join(', ');
  }
  
  function getAvatarUrl(user) {
    if (!user || !user.user_id) return 'https://telegram.org/img/t_logo.png';
    return `https://krksksoc-maman.up.railway.app/userpics/${user.user_id}.jpg`;
  }
</script>

<svelte:head>
  <title>Друзья и козлы</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</svelte:head>

<div class="container">
  <h2>👥 Друзья и козлы</h2>
  
  <div class="description">
    Оцените участников сообщества и посмотрите, кто вас как оценил.
  </div>
  
  <div class="anketa-section">
    <h3>Голосование</h3>
    
    {#if isAnketaLoading}
      <div class="loading">
        <div class="spinner"></div>
        <p>Загрузка анкеты...</p>
      </div>
    {:else if anketaError}
      <div class="error">
        <div class="error-icon">⚠️</div>
        <div class="error-message">{anketaError}</div>
      </div>
    {:else if anketaData}
      <div class="anketa-card">
        <div class="profile">
          <img 
            class="avatar" 
            src={getAvatarUrl(anketaData)} 
            alt="аватар"
            on:error={(e) => { e.target.src = 'https://telegram.org/img/t_logo.png'; }}
          />
          <div class="user-details">
            <div class="username">{anketaData.username ? '@' + anketaData.username : ''}</div>
            <div class="first-name">{anketaData.first_name || 'Неизвестно'}</div>
          </div>
        </div>
        
        <div class="vote-buttons">
          <button 
            class="vote-btn friend" 
            on:click={() => vote('friend')} 
            disabled={isVoting}
          >
            👥 Друг
          </button>
          <button 
            class="vote-btn neutral" 
            on:click={() => vote('neutral')} 
            disabled={isVoting}
          >
            😐 Нейтрально
          </button>
          <button 
            class="vote-btn foe" 
            on:click={() => vote('foe')} 
            disabled={isVoting}
          >
            👿 Козёл
          </button>
        </div>
        
        {#if isVoting}
          <div class="voting-status">Отправляем голос...</div>
        {/if}
      </div>
    {/if}
  </div>
  
  <div class="lists-section">
    <h3>Списки</h3>
    
    <div class="list-buttons">
      <button 
        class="list-btn" 
        class:active={showingLists}
        on:click={showMyLists}
      >
        📋 Мои списки
      </button>
      <button 
        class="list-btn" 
        class:active={showingWhoAddedMe}
        on:click={showWhoAddedMe}
      >
        👀 Кто меня добавил
      </button>
    </div>
    
    {#if listsError}
      <div class="error">
        <div class="error-icon">❌</div>
        <div class="error-message">{listsError}</div>
      </div>
    {:else if lists}
      <div class="lists-content">
        {#if showingLists}
          <div class="list-group">
            <div class="list-item friends">
              <div class="list-header">
                <span class="list-icon">👥</span>
                <span class="list-title">Друзья</span>
              </div>
              <div class="list-content">{getUsersNames(lists.friends)}</div>
            </div>
            
            <div class="list-item neutral">
              <div class="list-header">
                <span class="list-icon">😐</span>
                <span class="list-title">Нейтрально</span>
              </div>
              <div class="list-content">{getUsersNames(lists.neutral)}</div>
            </div>
            
            <div class="list-item foes">
              <div class="list-header">
                <span class="list-icon">👿</span>
                <span class="list-title">Козлы</span>
              </div>
              <div class="list-content">{getUsersNames(lists.foes)}</div>
            </div>
          </div>
        {/if}
        
        {#if showingWhoAddedMe}
          <div class="list-group">
            <div class="list-item friends">
              <div class="list-header">
                <span class="list-icon">👥</span>
                <span class="list-title">В друзья добавили</span>
              </div>
              <div class="list-content">{getUsersNames(lists.friends)}</div>
            </div>
            
            <div class="list-item neutral">
              <div class="list-header">
                <span class="list-icon">😐</span>
                <span class="list-title">В нейтралы добавили</span>
              </div>
              <div class="list-content">{getUsersNames(lists.neutral)}</div>
            </div>
            
            <div class="list-item foes">
              <div class="list-header">
                <span class="list-icon">👿</span>
                <span class="list-title">В козлы добавили</span>
              </div>
              <div class="list-content">{getUsersNames(lists.foes)}</div>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
  
  <div class="buttons">
    <button on:click={goBack}>🏠 На главную</button>
  </div>
</div>

<style>
  h2 {
    text-align: center;
    margin-top: 0;
    color: #333;
    margin-bottom: 16px;
  }
  
  h3 {
    color: #333;
    margin-bottom: 16px;
    font-size: 18px;
  }
  
  .description {
    text-align: center;
    color: #666;
    margin-bottom: 32px;
    font-size: 14px;
  }
  
  .anketa-section, .lists-section {
    margin-bottom: 32px;
  }
  
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 0;
    color: #666;
  }
  
  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #3b5998;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 12px;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .error {
    display: flex;
    align-items: center;
    padding: 16px;
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 12px;
    margin-bottom: 16px;
  }
  
  .error-icon {
    font-size: 20px;
    margin-right: 12px;
  }
  
  .error-message {
    color: #721c24;
  }
  
  .anketa-card {
    background: #f8f9fa;
    border-radius: 16px;
    padding: 24px;
    border: 1px solid #e9ecef;
  }
  
  .profile {
    display: flex;
    align-items: center;
    margin-bottom: 24px;
  }
  
  .avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    margin-right: 16px;
    border: 2px solid #e0e0e0;
    object-fit: cover;
  }
  
  .user-details {
    flex: 1;
  }
  
  .username {
    font-weight: 600;
    font-size: 16px;
    color: #333;
    margin-bottom: 4px;
  }
  
  .first-name {
    color: #666;
    font-size: 14px;
  }
  
  .vote-buttons {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }
  
  .vote-btn {
    flex: 1;
    padding: 12px 8px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .vote-btn.friend {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }
  
  .vote-btn.friend:hover {
    background: #c3e6cb;
  }
  
  .vote-btn.neutral {
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
  }
  
  .vote-btn.neutral:hover {
    background: #ffeaa7;
  }
  
  .vote-btn.foe {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }
  
  .vote-btn.foe:hover {
    background: #f5c6cb;
  }
  
  .vote-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .voting-status {
    text-align: center;
    color: #666;
    font-style: italic;
  }
  
  .list-buttons {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }
  
  .list-btn {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    background: white;
    color: #666;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .list-btn:hover {
    border-color: #3b5998;
    color: #3b5998;
  }
  
  .list-btn.active {
    background: #3b5998;
    color: white;
    border-color: #3b5998;
  }
  
  .list-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .list-item {
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #e9ecef;
  }
  
  .list-item.friends {
    background: #f8fff8;
    border-color: #c3e6cb;
  }
  
  .list-item.neutral {
    background: #fffef8;
    border-color: #ffeaa7;
  }
  
  .list-item.foes {
    background: #fff8f8;
    border-color: #f5c6cb;
  }
  
  .list-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }
  
  .list-icon {
    font-size: 18px;
    margin-right: 8px;
  }
  
  .list-title {
    font-weight: 600;
    color: #333;
  }
  
  .list-content {
    color: #666;
    font-size: 14px;
    line-height: 1.4;
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