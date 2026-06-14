document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('parcel-chat-toggle');
    const closeBtn = document.getElementById('parcel-chat-close');
    const windowBox = document.getElementById('parcel-chat-window');
    const form = document.getElementById('parcel-chat-form');
    const input = document.getElementById('parcel-chat-input');
    const messages = document.getElementById('parcel-chat-messages');
    const askStaffBtn = document.getElementById('ask-staff-btn');
    const loadStaffRepliesBtn = document.getElementById('load-staff-replies');

    if (!toggle || !windowBox || !form || !input || !messages) return;

    function addMessage(text, sender = 'bot') {
        const div = document.createElement('div');
        div.className = `chat-message ${sender}`;
        div.textContent = text;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    async function postJson(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });

        return response.json();
    }

    async function sendToBot(message) {
        addMessage(message, 'user');
        input.value = '';

        try {
            const data = await postJson('/chatbot/ask', {message});
            addMessage(data.reply || 'Sorry, I could not answer that.');
        } catch (error) {
            addMessage('Chat service is not available right now. Please try again later.');
        }
    }

    toggle.addEventListener('click', () => {
        windowBox.classList.toggle('open');
    });

    closeBtn.addEventListener('click', () => {
        windowBox.classList.remove('open');
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();

        const message = input.value.trim();

        if (message) {
            sendToBot(message);
        }
    });

    document.querySelectorAll('.quick-chat').forEach(button => {
        button.addEventListener('click', () => {
            sendToBot(button.dataset.message);
        });
    });

    askStaffBtn.addEventListener('click', async () => {
        const question = input.value.trim();

        if (!question) {
            addMessage('Type your question first, then click Ask staff.');
            return;
        }

        addMessage(question, 'user');
        input.value = '';

        try {
            const data = await postJson('/chatbot/ask_staff', {question});
            addMessage(data.reply || 'Your question was sent to staff.');
        } catch (error) {
            addMessage('Could not send your question to staff. Please login and try again.');
        }
    });

    loadStaffRepliesBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/chatbot/my_questions');
            const data = await response.json();

            if (!data.messages || data.messages.length === 0) {
                addMessage('No staff questions found for your account yet.');
                return;
            }

            data.messages.forEach(item => {
                const answer = item.answer ? item.answer : 'Waiting for staff reply.';
                addMessage(`Your question: ${item.question}\nStaff answer: ${answer}`);
            });
        } catch (error) {
            addMessage('Could not load staff replies right now.');
        }
    });
});