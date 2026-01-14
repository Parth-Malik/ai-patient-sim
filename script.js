const API_URL = '/chat';

// --- 1. SESSION MANAGEMENT ---
// Uses sessionStorage so every new tab gets a unique Patient ID.
// Re-opening the same tab keeps the conversation.
function getSessionID() {
    let id = sessionStorage.getItem('medsim_id');
    if (!id) {
        id = 'user_' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('medsim_id', id);
    }
    return id;
}

const threadId = getSessionID();
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const micBtn = document.getElementById('micBtn');

// --- 2. UI HELPER ---
function addMsg(text, type) {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- 3. SEND MESSAGE LOGIC ---
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 1. Show user message
    addMsg(text, 'user');
    userInput.value = '';

    // 2. Send to Backend
    try {
        const res = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: threadId })
        });
        
        const data = await res.json();
        
        // 3. Show Bot Response
        if (data.error) {
            addMsg("Error: " + data.error, 'bot');
        } else {
            addMsg(data.response, 'bot');
        }

    } catch (e) {
        addMsg("Connection Error. Is the server running?", 'bot');
    }
}

// --- 4. SPEECH RECOGNITION (VOICE TO TEXT) ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false; // Stop listening after one sentence
    recognition.lang = 'en-US';

    // Toggle recording on click
    micBtn.onclick = () => {
        if (micBtn.classList.contains('recording')) {
            recognition.stop();
        } else {
            recognition.start();
        }
    };

    // Visual cues
    recognition.onstart = () => {
        micBtn.classList.add('recording');
        userInput.placeholder = "Listening...";
    };

    recognition.onend = () => {
        micBtn.classList.remove('recording');
        userInput.placeholder = "Type your question here...";
        
        // Optional: Auto-send if text was captured
        if (userInput.value.trim().length > 0) {
            sendMessage();
        }
    };

    // Capture result
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
    };

} else {
    // If browser doesn't support speech, hide the mic button
    console.log("Web Speech API not supported.");
    if(micBtn) micBtn.style.display = 'none';
}

// --- 5. EVENT LISTENERS ---
// Send on Enter key
userInput.onkeypress = (e) => {
    if (e.key === 'Enter') sendMessage();
};

// Send on Button Click
document.getElementById('sendBtn').onclick = sendMessage;
