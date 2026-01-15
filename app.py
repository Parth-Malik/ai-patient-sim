import os
import random
import json
import re
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# --- LANGCHAIN IMPORTS ---
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Annotated
import operator

# --- 1. CONFIGURATION ---
load_dotenv()
keys = os.getenv("GROQ_API_KEYS")
API_KEYS = [k.strip() for k in keys.split(',')] if keys else ["dummy"]

app = Flask(__name__)
CORS(app)

# Global store to send patient details to frontend
patient_store = {} 

# --- 2. HELPER FUNCTIONS ---
def get_llm(temp=0.7):
    return ChatGroq(
        api_key=random.choice(API_KEYS), 
        model="llama-3.1-8b-instant", 
        temperature=temp
    )

def parse_json(text):
    text = re.sub(r'```json\s*|```', '', text).strip()
    start, end = text.find('{'), text.rfind('}') + 1
    return json.loads(text[start:end]) if start != -1 and end != -1 else {}

# --- 3. CREATOR AGENT (Generates Case) ---
def generate_patient():
    print("🧬 Generating FRESH patient case...")
    llm = get_llm(1.0) 
    
    prompt = """
    Create a detailed, realistic medical patient profile.
    
    RULES:
    1. AVOID common colds/flu. Pick distinct conditions (e.g., Carpal Tunnel, Sciatica, Gastritis, Vertigo, Eczema).
    2. "Speech Style" should be natural and descriptive (e.g., "Casual", "Detailed", "Polite but worried").
    
    Return ONLY valid JSON:
    {
        "name": "First Name",
        "age": Integer,
        "sex": "Male/Female",
        "disease": "Specific Condition",
        "visible_symptoms": ["Main Symptom", "Secondary Symptom"],
        "secret_symptom": "A critical clue (only reveal if specifically asked)",
        "pain_description": "Adjectives describing the pain (e.g. throbbing, sharp, dull, burning)",
        "speech_style": "Natural/Casual",
        "treatment": ["Correct Meds/Action"]
    }
    """
    
    try:
        p = parse_json(llm.invoke(prompt).content)
        if isinstance(p.get('visible_symptoms'), str): 
            p['visible_symptoms'] = [p['visible_symptoms']]
        print(f"✅ Created: {p['name']} - {p['disease']}")
        return p
    except Exception as e:
        print(f"⚠️ Generation Error: {e}")
        return {
            "name": "Alex", "age": 30, "sex": "Male",
            "disease": "Tension Headache", 
            "visible_symptoms": ["Headache", "Neck stiffness"], 
            "secret_symptom": "Stress at work", 
            "pain_description": "A tight band squeezing my head",
            "speech_style": "Tired",
            "treatment": ["Rest", "Ibuprofen"]
        }

def get_system_prompt(p):
    """
    The 'Descriptive but Natural' Prompt.
    """
    return f"""
    ROLE: You are {p['name']}, {p['age']} years old, {p['sex']}.
    
    === YOUR REALITY ===
    CONDITION: {p['disease']} (NEVER say this name).
    SYMPTOMS: {", ".join(p['visible_symptoms'])}.
    PAIN FEELS LIKE: {p.get('pain_description', 'uncomfortable')}.
    SECRET: {p['secret_symptom']} (Only tell if asked).
    
    === THE CURE ===
    The ONLY thing that helps is: {', '.join(p['treatment'])}.
    If the doctor suggests this:
    1. ACCEPT IT NATURALLY.
    2. Say something like: "That makes sense, I'll try that." or "Okay, thanks doc."
    
    === CONVERSATION STYLE (CRITICAL) ===
    1. BE DESCRIPTIVE, NOT DRAMATIC: Do not use *gasps* or *sighs*. Do not yell.
    2. USE SENSORY DETAILS: When asked about pain, describe *how* it feels. 
       - Bad: "It hurts."
       - Good: "It's a dull throbbing that won't go away." or "It feels like a burning sensation."
    3. NATURAL PHRASING: Speak like a normal person texting. You can use 2-3 sentences to explain yourself.
    4. START VAGUE: Mention the main issue first. Let the doctor ask follow-up questions.
    5. UNKNOWN: If asked about medical history not in your profile, just say "No" or "I don't think so."
    
    Start now. Wait for the doctor to speak.
    """

# --- 4. ACTOR AGENT (The Chatbot) ---
class State(TypedDict):
    messages: Annotated[List, operator.add]

def bot_node(state: State):
    # Temp 0.6 allows for descriptive language without going off-script
    try:
        return {"messages": [get_llm(0.6).invoke(state["messages"])]}
    except:
        return {"messages": [HumanMessage(content="...")]}

# Graph Setup
workflow = StateGraph(State)
workflow.add_node("patient", bot_node)
workflow.set_entry_point("patient")
workflow.add_edge("patient", END)
memory = MemorySaver()
agent = workflow.compile(checkpointer=memory)

# --- 5. ROUTES ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    uid, msg = data.get('thread_id'), data.get('message')
    
    if not uid or not msg: 
        return jsonify({"error": "Bad Request"}), 400
    
    config = {"configurable": {"thread_id": uid}}
    inputs = [HumanMessage(content=msg)]
    
    # Check if New User
    state = agent.get_state(config)
    if not state.values:
        print(f"✨ New Session: {uid}")
        p = generate_patient()
        patient_store[uid] = p 
        inputs = [SystemMessage(content=get_system_prompt(p))] + inputs
        
    try:
        res = agent.invoke({"messages": inputs}, config=config)
        
        return jsonify({
            "response": res["messages"][-1].content,
            "patient_info": {
                "name": patient_store.get(uid, {}).get("name", "Unknown"),
                "age": patient_store.get(uid, {}).get("age", "?"),
                "sex": patient_store.get(uid, {}).get("sex", "?")
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/<path:f>')
def static_files(f): return send_from_directory('.', f)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
