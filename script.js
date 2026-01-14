const API_URL = '/chat';

// --- SESSION LOGIC ---
// sessionStorage is unique per tab. 
// Opening a new tab = Empty sessionStorage = New ID = New Patient.
function getSessionID() {
    let id = sessionStorage.getItem('medsim_id');
    if (!id) {
        // Generate a random ID for this specific tab
        id = 'user_' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('medsim_id', id);
    }
    return id;
}

const threadId = getSessionID();
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');

// --- UI HELPER ---
function addMsg(text, type) {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- SEND MESSAGE ---
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMsg(text, 'user');
    userInput.value = '';

    try {
        const res = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: threadId })
        });
        
        const data = await res.json();
        
        if (data.error) {
            addMsg("Error: " + data.error, 'bot');
        } else {
            addMsg(data.response, 'bot');
            
            // OPTIONAL: Update header if you want to show patient details
            // check your console to see the new patient data coming in
            if (data.patient_info) {
                console.log("New Patient Data:", data.patient_info);
            }
        }

    } catch (e) {
        addMsg("Server Error", 'bot');
    }
}

// --- EVENTS ---
document.getElementById('sendBtn').onclick = sendMessage;
userInput.onkeypress = (e) => e.key === 'Enter' && sendMessage();
