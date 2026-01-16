

```markdown
<div align="center">

# 🩺 MedSim Pro
### The Autonomous Medical Training Environment

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/AI-Groq%20LPU-f55036?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

<br />

**MedSim Pro replaces expensive "Standardized Patients" with autonomous, generative AI agents.** *Infinite scenarios. Sub-400ms latency. Zero hallucinations.*

[View Demo](https://your-demo-link.com) · [Report Bug](https://github.com/yourusername/medsim-pro/issues) · [Request Feature](https://github.com/yourusername/medsim-pro/issues)

</div>

---

## 🏗️ System Architecture

MedSim Pro utilizes a **Microservices Architecture** to separate the user interface from the heavy AI orchestration.

```mermaid
graph TD
    User[👨‍⚕️ Medical Student] -->|HTTPS / REST| UI[💻 React Frontend (Vercel)]
    UI -->|API Requests| API[🐍 Flask Backend (Render)]
    
    subgraph "The AI Core (LangGraph)"
        API -->|State Management| State{StateGraph}
        State -->|1. Generate Profile| Creator[🤖 Creator Agent]
        State -->|2. Roleplay| Actor[🎭 Actor Agent]
        Creator -.->|Ground Truth JSON| Actor
    end
    
    Creator -->|Inference| Groq[⚡ Groq LPU (Llama 3.1)]
    Actor -->|Inference| Groq
    
    API -->|Persistence| DB[(💽 Hybrid Database)]
    DB -->|Primary| Mongo[MongoDB Atlas]
    DB -->|Circuit Breaker| RAM[In-Memory Fallback]

```

---

## 🚀 Key Features

### 🧠 Dual-Agent "No-Hallucination" System

Most medical chatbots make up symptoms. MedSim Pro uses a **Creator Agent** to generate a hidden "Ground Truth" profile (symptoms, history, vitals) before the chat starts. The **Actor Agent** is then strictly bound to this profile, ensuring medical accuracy.

### ⚡ The Hybrid Database (Circuit Breaker)

Designed for **100% Demo Uptime**. The system automatically detects database health:

1. **Primary:** Attempts to connect to **MongoDB Atlas**.
2. **Fallback:** If the cloud DB times out (common in serverless cold starts), it seamlessly switches to an **In-Memory RAM Store**.
3. **Result:** The application *never* crashes during a presentation.

### 💬 "Text-Message" Persona

Advanced prompt engineering prevents the AI from "over-acting" (e.g., `*sighs loudly*`). The patient communicates in short, lower-case, slightly frustrated messages—just like a real patient texting their doctor.

---

## 🛠️ Tech Stack

| Component | Technology | Why we chose it |
| --- | --- | --- |
| **Frontend** | React + Vite | Sub-200ms load times and component modularity. |
| **Backend** | Python Flask | Lightweight orchestrator for LangChain/LangGraph. |
| **AI Engine** | LangChain + Groq | Groq LPU delivers token speeds 10x faster than GPT-4. |
| **State Mgmt** | LangGraph | Maintains conversation context across long diagnostic sessions. |
| **Deployment** | Vercel + Render | Decoupled hosting for independent scaling. |

---

## ⚡ Quick Start

### Prerequisites

* Python 3.10+
* Node.js 18+
* Groq API Key (Get one [here](https://console.groq.com/))

### 1. Clone the Repo

```bash
git clone [https://github.com/yourusername/medsim-pro.git](https://github.com/yourusername/medsim-pro.git)
cd medsim-pro

```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "GROQ_API_KEY=your_key_here" > .env
echo "SECRET_KEY=dev_secret" >> .env

# Run Server
python app.py

```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
npm run dev

```

Visit `http://localhost:5173` to start diagnosing!

---

## 🔮 Roadmap

* [ ] **Voice Interaction:** Integration with OpenAI Whisper for voice-to-text diagnosis.
* [ ] **Teacher Dashboard:** Real-time grading of student performance vs. the "Ground Truth" profile.
* [ ] **Multi-Modal Support:** Ability for the AI to "upload" X-rays or Lab Results.

---

## 👤 Author

**Parth Malik**

---

<div align="center">
<sub>Built for ICAPP.</sub>
</div>

```

```
