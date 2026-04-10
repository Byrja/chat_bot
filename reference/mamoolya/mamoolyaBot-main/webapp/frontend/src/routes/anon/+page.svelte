<script>
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  
  let message = '';
  let result = '';
  let isLoading = false;
  
  async function submitAnon() {
    if (!message.trim()) {
      result = '❌ Сообщение не может быть пустым';
      return;
    }
    
    isLoading = true;
    result = '';
    
    try {
      const response = await api.sendAnon(message.trim());
      result = `✅ ${response.message}`;
      message = '';
    } catch (error) {
      result = `❌ ${error.message}`;
    } finally {
      isLoading = false;
    }
  }
  
  function goBack() {
    goto('/');
  }
</script>

<div class="container">
  <h2>📝 Анонимное признание</h2>
  
  <div class="description">
    Отправьте анонимное сообщение мамуле. Ваше имя не будет раскрыто.
  </div>
  
  <form on:submit|preventDefault={submitAnon}>
    <textarea 
      bind:value={message} 
      placeholder="Введите ваше признание..." 
      rows="5"
      required
    ></textarea>
    
    <button type="submit" disabled={isLoading}>
      {isLoading ? 'Отправляем...' : 'Отправить'}
    </button>
  </form>
  
  {#if result}
    <div class="result" class:success={result.startsWith('✅')} class:error={result.startsWith('❌')}>
      {result}
    </div>
  {/if}
  
  <div class="buttons">
    <button on:click={goBack} class="secondary">🏠 На главную</button>
  </div>
</div>

<style>
  h2 {
    text-align: center;
    margin-top: 0;
    color: #333;
    margin-bottom: 16px;
  }
  
  .description {
    text-align: center;
    color: #666;
    margin-bottom: 24px;
    font-size: 14px;
  }
  
  form {
    margin-bottom: 24px;
  }
  
  textarea {
    width: 100%;
    padding: 16px;
    border: 2px solid #e9ecef;
    border-radius: 12px;
    font-size: 16px;
    font-family: inherit;
    resize: vertical;
    margin-bottom: 16px;
    box-sizing: border-box;
    transition: border-color 0.3s ease;
  }
  
  textarea:focus {
    outline: none;
    border-color: #3b5998;
  }
  
  textarea::placeholder {
    color: #adb5bd;
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
  
  button:disabled {
    background: #adb5bd;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  
  .secondary {
    background: #6c757d;
    box-shadow: 0 2px 8px rgba(108, 117, 125, 0.3);
  }
  
  .secondary:hover {
    background: #5a6268;
    box-shadow: 0 4px 12px rgba(108, 117, 125, 0.4);
  }
  
  .result {
    padding: 16px;
    border-radius: 12px;
    margin-bottom: 24px;
    text-align: center;
    font-weight: 500;
  }
  
  .success {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }
  
  .error {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }
  
  .buttons {
    text-align: center;
  }
</style> 