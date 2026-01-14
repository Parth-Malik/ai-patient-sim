const API_URL = '/chat';

// 1. Generate a random user ID so the backend remembers this specific chat
let threadId = localStorage.getItem('userId');
if (!threadId) {
    threadId = 'user_' + Math.floor(Math.random() * 100000);
    localStorage.setItem('userId', threadId);
}

// 2. Grab HTML elements we need to control
const chatBox = document.getElementById('chatBox');
const inputField = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// 3. Helper function to add a bubble to the chat
function addMessage(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender); // adds class "message user" or "message bot"
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight; // Scroll to bottom
}

// 4. Main function to send data
async function sendMessage() {
    const text = inputField.value.trim();
    if (!text) return; // Don't send empty messages

    // Show user message immediately
    addMessage(text, 'user');
    inputField.value = ''; // Clear input

    try {
        // Send to Python backend
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: text, 
                thread_id: threadId 
            })
        });

        const data = await response.json();
        
        // Show bot response
        if (data.error) {
            addMessage("Error: " + data.error, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }

    } catch (error) {
        addMessage("Server error. Is the backend running?", 'bot');
    }
}

// 5. Add event listeners (Click button OR press Enter)
sendBtn.addEventListener('click', sendMessage);

inputField.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
