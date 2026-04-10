<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  
  // Список знаков зодиака
  const zodiacSigns = [
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"
  ];
  
  // Переменные состояния
  let selectedSign = null;
  let currentSign = null;
  let loading = false;
  let error = null;
  let success = null;
  
  // Получаем текущий знак зодиака при загрузке страницы
  onMount(async () => {
    try {
      const data = await api.getZodiac();
      
      if (data.zodiac_sign) {
        currentSign = data.zodiac_sign;
        selectedSign = data.zodiac_sign;
      }
    } catch (err) {
      console.error('Ошибка при получении знака зодиака:', err);
      error = 'Не удалось загрузить текущий знак зодиака';
    }
  });
  
  // Функция для выбора знака зодиака
  function selectSign(sign) {
    selectedSign = sign;
  }
  
  // Функция для сохранения выбранного знака зодиака
  async function saveZodiac() {
    if (!selectedSign) {
      error = 'Пожалуйста, выберите знак зодиака';
      return;
    }
    
    loading = true;
    error = null;
    success = null;
    
    try {
      const data = await api.setZodiac(selectedSign);
      success = data.message;
      currentSign = selectedSign;
    } catch (err) {
      console.error('Ошибка при сохранении знака зодиака:', err);
      error = err.message || 'Не удалось сохранить знак зодиака';
    } finally {
      loading = false;
    }
  }
  
  // Функция для возврата на главную страницу
  function goHome() {
    goto('/');
  }
</script>

<div class="container">
  <h1>🔮 Выбор знака зодиака</h1>
  
  <div class="current-sign" class:visible={currentSign}>
    {#if currentSign}
      <p>Ваш текущий знак зодиака: <strong>{currentSign}</strong></p>
    {/if}
  </div>
  
  <div class="instructions">
    <p>Выберите свой знак зодиака, чтобы получать персональный гороскоп от Мамули!</p>
  </div>
  
  <div class="zodiac-grid">
    {#each zodiacSigns as sign}
      <div 
        class="zodiac-sign" 
        class:selected={selectedSign === sign}
        on:click={() => selectSign(sign)}
      >
        {sign}
      </div>
    {/each}
  </div>
  
  <div class="actions">
    <button 
      class="save-button" 
      disabled={loading || !selectedSign || selectedSign === currentSign}
      on:click={saveZodiac}
    >
      {loading ? 'Сохранение...' : 'Сохранить'}
    </button>
    
    <button class="back-button" on:click={goHome}>
      Назад
    </button>
  </div>
  
  {#if error}
    <div class="message error">
      {error}
    </div>
  {/if}
  
  {#if success}
    <div class="message success">
      {success}
    </div>
  {/if}
</div>

<style>
  .container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }
  
  h1 {
    text-align: center;
    color: #333;
    margin-bottom: 30px;
  }
  
  .current-sign {
    text-align: center;
    margin-bottom: 20px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
    border: 1px solid #e9ecef;
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  
  .current-sign.visible {
    opacity: 1;
  }
  
  .instructions {
    text-align: center;
    color: #666;
    margin-bottom: 30px;
    font-size: 16px;
  }
  
  .zodiac-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 15px;
    margin-bottom: 30px;
  }
  
  .zodiac-sign {
    padding: 20px 10px;
    text-align: center;
    background: #fff;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
    font-weight: 500;
  }
  
  .zodiac-sign:hover {
    border-color: #3b5998;
    background: #f8f9ff;
  }
  
  .zodiac-sign.selected {
    border-color: #3b5998;
    background: #3b5998;
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 89, 152, 0.3);
  }
  
  .actions {
    display: flex;
    gap: 15px;
    justify-content: center;
    margin-bottom: 20px;
  }
  
  button {
    padding: 12px 24px;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .save-button {
    background: #3b5998;
    color: white;
  }
  
  .save-button:hover:not(:disabled) {
    background: #2d4373;
    transform: translateY(-2px);
  }
  
  .save-button:disabled {
    background: #ccc;
    cursor: not-allowed;
    transform: none;
  }
  
  .back-button {
    background: #6c757d;
    color: white;
  }
  
  .back-button:hover {
    background: #5a6268;
    transform: translateY(-2px);
  }
  
  .message {
    padding: 15px;
    border-radius: 6px;
    text-align: center;
    margin-bottom: 15px;
  }
  
  .error {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }
  
  .success {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }
</style>