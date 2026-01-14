const API_URL = '/chat';

// --- 1. TOKEN / SESSION MANAGEMENT ---
// We use sessionStorage instead of localStorage.
// sessionStorage is CLEARED when the tab is closed.
// This guarantees a new patient every time you open a new tab.
function getSessionToken() {
    let token = sessionStorage.getItem('medsim_token');
    if (!token) {
        // Generate a random unique token for this tab
        token = 'user_' + Math.floor(Math.random() * 1000000);
        sessionStorage.setItem('medsim_token', token);
    }
    return token;
}

const threadId = getSessionToken(); // This is your unique session token
const chatBox = document.getElementById('chatBox');
const inputField = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
// Grab the mic button (if it exists in your HTML)
const micBtn = document.getElementById('micBtn'); 

// --- 2. UI HELPER ---
function addMessage(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender); 
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight; 
}

// --- 3. SEND MESSAGE LOGIC ---
async function sendMessage() {
    const text = inputField.value.trim();
    if (!text) return; 

    // 1. Show user message
    addMessage(text, 'user');
    inputField.value = ''; 

    try {
        // 2. Send to Backend with our Unique Token
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: text, 
                thread_id: threadId // <--- The backend uses this to identify the patient
            })
        });

        const data = await response.json();
        
        // 3. Show bot response
        if (data.error) {
            addMessage("Error: " + data.error, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }

    } catch (error) {
        addMessage("Server error. Is the backend running?", 'bot');
    }
}

// --- 4. SPEECH RECOGNITION (Voice to Text) ---
// Checks if the browser supports speech (Chrome/Edge/Safari)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition && micBtn) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false; // Stop listening after one sentence
    recognition.lang = 'en-US';

    micBtn.onclick = () => {
        if (micBtn.classList.contains('recording')) {
            recognition.stop();
        } else {
            recognition.start();
        }
    };

    recognition.onstart = () => {
        micBtn.classList.add('recording');
        inputField.placeholder = "Listening...";
    };

    recognition.onend = () => {
        micBtn.classList.remove('recording');
        inputField.placeholder = "Type your question here...";
        // Optional: Auto-send if voice captured text
        if (inputField.value.trim().length > 0) {
            sendMessage();
        }
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        inputField.value = transcript;
    };
} else if (micBtn) {
    console.log("Web Speech API not supported.");
    micBtn.style.display = 'none'; // Hide button if not supported
}

// --- 5. EVENT LISTENERS ---
sendBtn.addEventListener('click', sendMessage);

inputField.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
