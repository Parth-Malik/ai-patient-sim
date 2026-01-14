// Determine the API URL (works for local and Vercel)
const API_URL = '/chat';

// --- SESSION MANAGEMENT ---
// This generates a unique ID for each browser/tab.
// This is the "Multi-User" feature in action.
function getSessionId() {
    let id = localStorage.getItem('patient_sim_id');
    if (!id) {
        id = 'user_' + Math.random().toString(36).substring(2, 9);
        localStorage.setItem('patient_sim_id', id);
    }
    return id;
}

const threadId = getSessionId();
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const typingIndicator = document.getElementById('typingIndicator');

// --- UI FUNCTIONS ---

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function setTyping(isTyping) {
    if (isTyping) {
        typingIndicator.classList.add('active');
    } else {
        typingIndicator.classList.remove('active');
    }
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Optimistic UI Update
    addMessage(text, 'user');
    userInput.value = '';
    setTyping(true);

    try {
        // 2. Send to Backend
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: text, 
                thread_id: threadId 
            })
        });

        const data = await response.json();
        setTyping(false);

        // 3. Handle Response
        if (data.error) {
            addMessage("⚠️ Error: " + data.error, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }
    } catch (error) {
        setTyping(false);
        addMessage("❌ Connection Error. Is the server running?", 'bot');
    }
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});