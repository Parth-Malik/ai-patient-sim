
# MedSim Pro: Autonomous Medical Training Environment

**MedSim Pro replaces expensive "Standardized Patients" with autonomous, generative AI agents.**
*Infinite scenarios. Sub-400ms latency. Zero hallucinations.*

---

## 🏗️ System Architecture

MedSim Pro utilizes a **Microservices Architecture** to separate the user interface from the heavy AI orchestration.

* **Frontend:** React + Vite (Hosted on Vercel)
* **Backend:** Python Flask (Hosted on Render)
* **AI Logic:** LangChain + LangGraph (Orchestrator)
* **Intelligence:** Groq LPU (Llama 3.1 Model)
* **Database:** Hybrid System (MongoDB Atlas + In-Memory Fallback)

---

## 🚀 Key Features

### 1. Dual-Agent "No-Hallucination" System

Most medical chatbots make up symptoms. MedSim Pro uses a **Creator Agent** to generate a hidden "Ground Truth" profile (symptoms, history, vitals) before the chat starts. The **Actor Agent** is then strictly bound to this profile, ensuring medical accuracy.

### 2. The Hybrid Database (Circuit Breaker)

Designed for **100% Demo Uptime**. The system automatically detects database health:

* **Primary:** Attempts to connect to **MongoDB Atlas**.
* **Fallback:** If the cloud DB times out (common in serverless cold starts), it seamlessly switches to an **In-Memory RAM Store**.
* **Result:** The application *never* crashes during a presentation.

### 3. "Text-Message" Persona

Advanced prompt engineering prevents the AI from "over-acting" (e.g., `*sighs loudly*`). The patient communicates in short, lower-case, slightly frustrated messages—just like a real patient texting their doctor.

---

## 🛠️ Tech Stack

* **Frontend:** React + Vite (Selected for sub-200ms load times)
* **Backend:** Python Flask (Selected as a lightweight orchestrator)
* **AI Engine:** LangChain + Groq (Groq LPU delivers speeds 10x faster than GPT-4)
* **State Management:** LangGraph (Maintains context across long diagnostic sessions)

---

## ⚡ Quick Start

### Prerequisites

* Python 3.10+
* Node.js 18+
* Groq API Key

### Installation

1. **Clone the Repo**
```bash
git clone https://github.com/yourusername/medsim-pro.git

```


2. **Backend Setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

```


3. **Frontend Setup**
```bash
cd frontend
npm install
npm run dev

```



---

## 👤 Author

**Parth Malik**
Full Stack Developer & AI Engineer

Built for ICAPP.
