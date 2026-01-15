const API_URL = ''; // Leave empty if serving from the same domain 

// --- STATE MANAGEMENT ---
let isLoginMode = true;
// We get the patient session ID from storage, or generate a new one if it's a new tab
let currentThreadId = sessionStorage.getItem('medsim_thread_id') || generateThreadId();

// --- DOM ELEMENTS ---
const authContainer = document.getElementById('authContainer');
const appContainer = document.getElementById('appContainer');
const authTitle = document.getElementById('authTitle');
const authError = document.getElementById('authError');
const userIn = document.getElementById('authUsername');
const passIn = document.getElementById('authPassword');
const docName = document.getElementById('doctorNameDisplay');
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// --- INITIALIZATION ---
// Check if user is already logged in
const savedUser = localStorage.getItem('medsim_user');
if (savedUser) {
    showApp(JSON.parse(savedUser));
}

// --- AUTHENTICATION LOGIC ---

function toggleAuthMode() {
    isLoginMode = !isLoginMode;
    authTitle.innerText = isLoginMode ? "Doctor Login" : "Create Profile";
    authError.innerText = "";
}

async function handleLogin() {
    const endpoint = isLoginMode ? '/login' : '/register';
    const username = userIn.value.trim();
    const password = passIn.value.trim();

    if (!username || !password) {
        authError.innerText = "Please fill all fields.";
        return;
    }

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();

        if (res.ok) {
            // Save user info to LocalStorage
            const userData = { id: data.user_id, name: username, token: data.token };
            localStorage.setItem('medsim_user', JSON.stringify(userData));
            showApp(userData);
        } else {
            authError.innerText = data.error || "Authentication failed.";
        }
    } catch (e) {
        console.error(e);
        authError.innerText = "Server connection error.";
    }
}

function showApp(user) {
    // Hide Login, Show Chat
    authContainer.classList.add('hidden');
    appContainer.classList.remove('hidden');
    docName.innerText = "Dr. " + user.name;
    
    // Optional: Load previous sessions logic here if you want
    // loadHistory; 
}

function logout() {
    localStorage.removeItem('medsim_user');
    location.reload(); // Refreshes page to show login screen
}

// --- SESSION LOGIC ---

function generateThreadId() {
    // Creates a random ID like 'case_abc123'
    const id = 'case_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('medsim_thread_id', id);
    return id;
}

function startNewSession() {
    // Clear the current patient ID so a new one is generated on reload
    sessionStorage.removeItem('medsim_thread_id');
    location.reload();
}

// --- CHAT LOGIC ---

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Get current logged-in user
    const user = JSON.parse(localStorage.getItem('medsim_user'));
    
    if (!user) {
        alert("Session expired. Please login again.");
        logout();
        return;
    }

    // Show User Message
    addMessage(text, 'user');
    userInput.value = '';

    // Send to Backend
    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,          // Doctor ID
                thread_id: currentThreadId, // Patient ID
                message: text
            })
        });
        
        const data = await res.json();
        
        if (data.error) {
            addMessage("Error: " + data.error, 'bot');
        } else {
            addMessage(data.response, 'bot');
        }
    } catch (e) {
        addMessage("Connection error. Is server running?", 'bot');
    }
}

function addMessage(text, role) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- EVENT LISTENERS ---
// Send on Button Click
sendBtn.onclick = sendMessage;
// Send on Enter Key
userInput.onkeypress = (e) => {
    if (e.key === 'Enter') sendMessage();
};

// --- HISTORY LOGIC ---

async function toggleHistory() {
    const sidebar = document.getElementById('historySidebar');
    const list = document.getElementById('historyList');
    
    // Toggle Class
    if (sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        return;
    }
    
    sidebar.classList.add('open');
    
    // Fetch Data
    const user = JSON.parse(localStorage.getItem('medsim_user'));
    if (!user) return;

    list.innerHTML = '<p style="text-align:center; color:#666;">Loading records...</p>';

    try {
        const res = await fetch(`/sessions/${user.id}`);
        const data = await res.json();
        
        if (data.length === 0) {
            list.innerHTML = '<p style="text-align:center; color:#666;">No patients treated yet.</p>';
            return;
        }

        // Render List
        let html = '';
        data.forEach(session => {
            // Note: The backend might not send 'date' in the simplified version, 
            // but if it does, you can use it.
            html += `
                <div class="history-item">
                    <h4>${session.patient}</h4>
                    <p>Diagnosis: <strong>${session.disease}</strong></p>
                    <div class="date">Case ID: ${session.thread_id}</div>
                </div>
            `;
        });
        list.innerHTML = html;

    } catch (e) {
        list.innerHTML = '<p style="color:red; text-align:center;">Failed to load history.</p>';
    }
}
