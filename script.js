const API_URL = '/chat';

// --- SESSION MANAGEMENT ---
function getSessionToken() {
    let token = sessionStorage.getItem('medsim_token');
    if (!token) {
        token = 'user_' + Math.floor(Math.random() * 1000000);
        sessionStorage.setItem('medsim_token', token);
    }
    return token;
}

let threadId = getSessionToken();
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const inputArea = document.getElementById('inputArea');
const endOverlay = document.getElementById('endOverlay');

// --- NEW FEATURES ---

// 1. Start New Session
function startNewSession() {
    // Clear the token to force a new patient on reload
    sessionStorage.removeItem('medsim_token');
    // Reload page
    location.reload();
}

// 2. End Session
function endSession() {
    // Disable inputs
    userInput.disabled = true;
    sendBtn.disabled = true;
    inputArea.classList.add('disabled');
    
    // Show Overlay
    endOverlay.classList.remove('hidden');
}

// --- CHAT LOGIC ---

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    userInput.value = '';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: threadId })
        });

        const data = await response.json();
        
        if (data.error) {
            addMessage("Error: " + data.error, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }

    } catch (error) {
        addMessage("Server Error", 'bot');
    }
}

// --- EVENT LISTENERS ---
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
