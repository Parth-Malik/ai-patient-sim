import os
import random
import json
import re
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Annotated
import operator

# --- Config ---
load_dotenv()
keys = os.getenv("GROQ_API_KEYS")
API_KEYS = [k.strip() for k in keys.split(',')] if keys else ["dummy"]

app = Flask(__name__)
CORS(app)

# --- Helpers ---
def get_llm(temp=0.7):
    # Rotate keys for load balancing
    return ChatGroq(api_key=random.choice(API_KEYS), model="llama-3.1-8b-instant", temperature=temp)

def parse_json(text):
    # Clean markdown and extract valid JSON
    text = re.sub(r'```json\s*|```', '', text).strip()
    start, end = text.find('{'), text.rfind('}') + 1
    return json.loads(text[start:end]) if start != -1 and end != -1 else {}

# --- Creator Agent (The Infinite Generator) ---
def generate_patient():
    print("Generating FRESH patient profile...")
    llm = get_llm(1.0) # High temp = High creativity
    
    prompt = """
    Invent a completely unique medical patient case. Do NOT reuse common diseases like Flu/Cold.
    Pick rare or specific conditions (e.g., Vertigo, Gout, Appendicitis, Cluster Headache).
    
    Return ONLY valid JSON:
    {
        "name": "First Name",
        "age": Integer,
        "disease": "Specific Condition Name",
        "visible_symptoms": ["Main Symptom", "Secondary Symptom", "Other Sign"],
        "secret_symptom": "Critical clue revealed only if asked",
        "red_flags": "Emergency sign (e.g. fainting)",
        "treatment": ["Correct Medication/Action"],
        "personality": "Civil, direct, brief (e.g. Stoic, Anxious, Blunt)"
    }
    Constraint: "visible_symptoms" must have at least 3 distinct items.
    """
    
    try:
        raw_output = llm.invoke(prompt).content
        profile = parse_json(raw_output)
        
        # Ensure symptoms are a list
        if isinstance(profile.get('visible_symptoms'), str): 
            profile['visible_symptoms'] = [profile['visible_symptoms']]
            
        print(f"✅ Created: {profile['name']} - {profile['disease']}")
        return profile
    except Exception as e:
        print(f"⚠️ Gen Failed: {e}")
        # Emergency backup only
        return {
            "name": "Alex", "age": 30, "disease": "Unknown Viral Infection",
            "visible_symptoms": ["Fever", "Rash", "Fatigue"],
            "secret_symptom": "Travelled recently", "red_flags": "None",
            "treatment": ["Fluids"], "personality": "Direct"
        }

def get_system_prompt(p):
    return f"""
    ROLE: You are {p['name']} ({p['age']}). 
    CONDITION: {p['disease']} (NEVER reveal this name).
    SYMPTOMS: {", ".join(p['visible_symptoms'])}.
    HIDDEN: {p['secret_symptom']} (Reveal only if asked).
    TREATMENT: {", ".join(p['treatment'])}.
    
    INSTRUCTIONS:
    1. Speak normally. Be brief and civil. No storytelling.
    2. Start by stating your MAIN symptom only (e.g. "My head hurts.").
    3. If asked for more, list the other symptoms briefly.
    4. If asked about history/pain, answer truthfully based on your condition.
    5. If the doctor gives the correct TREATMENT, say "Okay, thanks."
    6. If the doctor is wrong/rude, correct them briefly.
    """

# --- Actor Agent (The Chatbot) ---
class State(TypedDict):
    messages: Annotated[List, operator.add]

def bot_node(state: State):
    # Temp 0.5 keeps behavior consistent but phrasing natural
    try:
        return {"messages": [get_llm(0.5).invoke(state["messages"])]}
    except:
        return {"messages": [HumanMessage(content="...")]}

flow = StateGraph(State)
flow.add_node("patient", bot_node)
flow.set_entry_point("patient")
flow.add_edge("patient", END)
agent = flow.compile(checkpointer=MemorySaver())

# --- Routes ---
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    uid, msg = data.get('thread_id'), data.get('message')
    
    if not uid or not msg: return jsonify({"error": "Bad Request"}), 400
    
    config = {"configurable": {"thread_id": uid}}
    inputs = [HumanMessage(content=msg)]
    
    # Check history. If empty -> New Patient
    state = agent.get_state(config)
    if not state.values:
        print(f"✨ New User Session: {uid}")
        p = generate_patient()
        inputs = [SystemMessage(content=get_system_prompt(p))] + inputs
        
    try:
        res = agent.invoke({"messages": inputs}, config=config)
        return jsonify({"response": res["messages"][-1].content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Static File Serving (Vercel/Local)
@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/<path:f>')
def static_files(f): return send_from_directory('.', f)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
