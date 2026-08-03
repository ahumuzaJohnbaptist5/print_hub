// static/js/chat_widget.js

document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('ph-chat-toggle');
    const chatWindow = document.getElementById('ph-chat-window');
    const closeBtn = document.getElementById('ph-chat-close');
    const iconChat = document.getElementById('ph-icon-chat');
    const iconClose = document.getElementById('ph-icon-close');
    const form = document.getElementById('ph-chat-form');
    const input = document.getElementById('ph-chat-input');
    const messagesContainer = document.getElementById('ph-chat-messages');
    const typingIndicator = document.getElementById('ph-typing-indicator');

    // --- 1. CSRF Token Handling (Crucial for Django) ---
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // --- 2. UI Toggle Logic ---
    const toggleChat = () => {
        chatWindow.classList.toggle('hidden');
        iconChat.classList.toggle('hidden');
        iconClose.classList.toggle('hidden');
        if (!chatWindow.classList.contains('hidden')) {
            input.focus();
        }
    };

    toggleBtn.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);

    // --- 3. Message Rendering ---
    const appendMessage = (text, isUser = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `flex gap-2 items-start ${isUser ? 'justify-end' : ''}`;
        
        if (!isUser) {
            msgDiv.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shrink-0">AI</div>
                <div class="bg-slate-700 text-slate-200 p-3 rounded-lg rounded-tl-none max-w-[80%] text-sm">${text}</div>
            `;
        } else {
            msgDiv.innerHTML = `
                <div class="bg-indigo-600 text-white p-3 rounded-lg rounded-tr-none max-w-[80%] text-sm">${text}</div>
            `;
        }
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    };

    // --- 4. Quick Action Chips ---
    document.querySelectorAll('.ph-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const text = chip.textContent.trim();
            appendMessage(text, true);
            sendMessage(text);
        });
    });

    // --- 5. Core API Communication ---
    const sendMessage = async (message) => {
        input.value = '';
        typingIndicator.classList.remove('hidden');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            const response = await fetch('/api/assistant/', { // Ensure this matches your urls.py
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ 
                    message: message,
                    context: window.location.pathname // Send current page for context awareness!
                })
            });

            const data = await response.json();
            typingIndicator.classList.add('hidden');

            if (data.reply) {
                appendMessage(data.reply);
            } else if (data.card) {
                // Handle Rich Cards (e.g., Order Status)
                appendMessage(data.card); 
            }

        } catch (error) {
            typingIndicator.classList.add('hidden');
            appendMessage("⚠️ I'm having trouble connecting to the server. Please try again later.");
            console.error("Chat Error:", error);
        }
    };

    // --- 6. Form Submission ---
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (text) {
            appendMessage(text, true);
            sendMessage(text);
        }
    });
});
