// script.js for v2 chatbot UI

document.addEventListener('DOMContentLoaded', () => {
  const chatContainer = document.getElementById('chatContainer');
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');

  // Helper to create a message bubble
  function addMessage(content, sender = 'bot') {
    const bubble = document.createElement('div');
    const isBot = sender === 'bot';
    bubble.className = `max-w-xs px-4 py-2 rounded-lg ${isBot ? 'bg-gray-200 text-gray-800 self-start' : 'bg-indigo-600 text-white self-end'} shadow`;
    bubble.textContent = content;
    chatContainer.appendChild(bubble);
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Initial welcome message from bot
  addMessage('Hello! I am your friendly chatbot. How can I help you today?', 'bot');

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const userMsg = messageInput.value.trim();
    if (!userMsg) return;
    addMessage(userMsg, 'user');
    messageInput.value = '';

    // Simulate bot reply after short delay
    setTimeout(() => {
      addMessage(`You said: "${userMsg}"`, 'bot');
    }, 500);
  });
});

