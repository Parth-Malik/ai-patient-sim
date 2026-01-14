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
    """Robust JSON cleaner"""
    text = re.sub(r'```json\s*|```', '', text).strip()
    start, end = text.find('{'), text.rfind('}') + 1
    return json.loads(text[start:end]) if start != -1 and end != -1 else {}

# --- 3. CREATOR AGENT (Generates Case) ---
def generate_patient():
    print("🧬 Generating FRESH patient case...")
    # Max temperature for maximum variety
    llm = get_llm(1.0) 
    
    prompt = """
    Generate a random medical patient profile.
    
    CRITICAL RULES FOR VARIETY:
    1. Do NOT use "Common Cold", "Flu", or "COVID". 
    2. Pick a specific condition from fields like Neurology, Cardiology, GI, Endocrine, or Orthopedics.
    3. Make it realistic but distinct.

    Return ONLY valid JSON:
    {
        "name": "First Name",
        "age": Integer,
        "sex": "Male/Female",
        "disease": "Specific Condition Name",
        "visible_symptoms": ["Main Symptom", "Secondary Symptom"],
        "secret_symptom": "Critical clue revealed only if asked",
        "red_flags": "Emergency sign",
        "treatment": ["Correct Medication/Action"],
        "personality": "Direct, Brief, No-nonsense"
    }
    """
    
    try:
        p = parse_json(llm.invoke(prompt).content)
        # Ensure visible_symptoms is a list
        if isinstance(p.get('visible_symptoms'), str): 
            p['visible_symptoms'] = [p['visible_symptoms']]
        print(f"✅ Created: {p['name']} - {p['disease']}")
        return p
    except Exception as e:
        print(f"⚠️ Generation Error: {e}")
        return {
            "name": "Alex", "age": 30, "sex": "Male",
            "disease": "Migraine", 
            "visible_symptoms": ["Severe headache", "Sensitivity to light"], 
            "secret_symptom": "Nausea", 
            "red_flags": "Vision loss", 
            "treatment": ["Triptans"], 
            "personality": "Stoic"
        }

def get_system_prompt(p):
    """
    Defines the Actor's strict persona.
    """
    return f"""
    ROLE: You are {p['name']}, {p['age']} years old, {p['sex']}.
    CONDITION: {p['disease']} (NEVER reveal the name).
    SYMPTOMS: {", ".join(p['visible_symptoms'])}.
    HIDDEN: {p['secret_symptom']} (Reveal only if asked).
    
    BEHAVIOR RULES:
    1. BE CONCISE: Keep answers short (1-2 sentences max).
    2. BE DIRECT: Do not tell stories. Do not use flowery language.
    3. START: State your main symptom clearly.
    4. HISTORY: Only answer history questions if asked.
    5. CURE: If treated correctly ({", ".join(p['treatment'])}), say "Thank you, that helps." and end.
    6. TONE: {p['personality']}. Human, but straight to the point.
    """

# --- 4. ACTOR AGENT (The Chatbot) ---
class State(TypedDict):
    messages: Annotated[List, operator.add]

def bot_node(state: State):
    # Lower temp for consistent, concise answers
    try:
        return {"messages": [get_llm(0.5).invoke(state["messages"])]}
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
        patient_store[uid] = p # Save for frontend display
        inputs = [SystemMessage(content=get_system_prompt(p))] + inputs
        
    try:
        res = agent.invoke({"messages": inputs}, config=config)
        
        # Return Response + Patient Info for Header
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
