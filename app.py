import os
import uuid
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
keys_env = os.getenv("GROQ_API_KEYS")
if not keys_env:
    API_KEYS = ["dummy"]
else:
    API_KEYS = [k.strip() for k in keys_env.split(',') if k.strip()]

app = Flask(__name__)
CORS(app)

# --- 2. THE CREATOR AGENT (Generates Patients) ---
def get_random_llm(temperature=0.7):
    """Helper to get a fresh model instance with a random key"""
    active_key = random.choice(API_KEYS)
    return ChatGroq(
        api_key=active_key,
        model="llama-3.1-8b-instant",
        temperature=temperature
    )

def clean_and_parse_json(text):
    """
    CLEANER FUNCTION: Strips markdown (```json ... ```) from LLM output
    to prevent JSON parsing errors.
    """
    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)
    text = text.strip()
    
    # Extract just the JSON object (between first { and last })
    start = text.find('{')
    end = text.rfind('}') + 1
    if start != -1 and end != -1:
        text = text[start:end]
        
    return json.loads(text)

def generate_unique_patient():
    print("🧬 CREATOR AGENT: Inventing a new patient profile...")
    
    # Use max temperature for maximum variety
    creator_model = get_random_llm(temperature=1.0)
    
    prompt = """
    You are a Medical Simulation Architect.
    Generate a unique, challenging patient case.
    
    Return ONLY a valid JSON object with these exact keys:
    {
        "name": "First Name",
        "age": Integer,
        "disease": "Medical Condition Name",
        "visible_symptoms": ["Symptom 1", "Symptom 2", "Symptom 3", "Symptom 4"],
        "secret_symptom": "A critical symptom revealed only if asked",
        "red_flags": "Emergency sign (e.g. fainting)",
        "treatment": ["Correct Meds", "Correct Action"],
        "personality": "One word mood (e.g. Anxious, Grumpy)"
    }
    
    CONSTRAINTS:
    1. "visible_symptoms" MUST contain at least 3 distinct items.
    2. Do NOT use markdown. Do NOT write "Here is the JSON". Just the raw JSON.
    """
    
    try:
        response = creator_model.invoke(prompt)
        # Use the robust cleaner
        profile = clean_and_parse_json(response.content)
        
        # Double check symptoms is a list
        if isinstance(profile.get('visible_symptoms'), str):
            profile['visible_symptoms'] = [profile['visible_symptoms']]
            
        print(f"✅ CREATED: {profile['name']} - {profile['disease']}")
        return profile
    except Exception as e:
        print(f"⚠️ Creation Failed: {e}. Falling back to backup.")
        return {
            "name": "Fallback Frank",
            "age": 55,
            "disease": "Chronic Bronchitis",
            "visible_symptoms": ["Heavy cough", "Wheezing", "Fatigue"],
            "secret_symptom": "Smokes 2 packs a day",
            "red_flags": "Blue lips",
            "treatment": ["Inhaler", "Quit smoking"],
            "personality": "Defensive"
        }

def build_system_prompt(profile):
    """
    Converts the JSON profile into the Actor's instructions.
    """
    symptoms_list = ", ".join(profile['visible_symptoms'])
    
    return f"""
    SYSTEM ROLE: You are a patient named {profile['name']} ({profile['age']} years old).
    
    === YOUR HIDDEN TRUTH ===
    CONDITION: {profile['disease']}
    VISIBLE SYMPTOMS: {symptoms_list}
    HIDDEN SYMPTOM (Hide this! Only reveal if asked): {profile['secret_symptom']}
    RED FLAG (Escalate if this happens): {profile['red_flags']}
    CORRECT TREATMENT: {', '.join(profile['treatment'])}
    PERSONALITY: {profile['personality']}
    
    === RULES ===
    1. ACTING: Stay in character ({profile['personality']}). Use plain English.
    2. REVEALING: Start by mentioning your MAIN symptom. If asked "what else?", list the rest.
    3. LYING: Do NOT say your disease name. If asked "Do you have {profile['disease']}?", say "I don't know."
    4. CURE: If the doctor prescribes a CORRECT TREATMENT, accept it.
    5. FAIL: If the doctor is rude or wrong, get annoyed.
    
    Start the conversation now.
    """

# --- 3. THE ACTOR AGENT (Simulates the Patient) ---
class AgentState(TypedDict):
    messages: Annotated[List, operator.add]

def brain_node(state: AgentState):
    messages = state["messages"]
    model = get_random_llm(temperature=0.6)
    
    try:
        response = model.invoke(messages)
        return {"messages": [response]}
    except Exception as e:
        return {"messages": [HumanMessage(content="...")]}

# Graph Setup
workflow = StateGraph(AgentState)
workflow.add_node("patient", brain_node)
workflow.set_entry_point("patient")
workflow.add_edge("patient", END)
memory = MemorySaver()
agent = workflow.compile(checkpointer=memory)

# --- 4. FLASK ROUTES ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message')
    thread_id = data.get('thread_id')

    if not user_input or not thread_id:
        return jsonify({"error": "Bad Request"}), 400

    config = {"configurable": {"thread_id": thread_id}}
    inputs = [HumanMessage(content=user_input)]
    
    current_state = agent.get_state(config)
    
    # If NO history, call the CREATOR AGENT
    if not current_state.values or not current_state.values.get("messages"):
        print(f"✨ New User {thread_id} detected.")
        patient_profile = generate_unique_patient()
        sys_prompt = build_system_prompt(patient_profile)
        inputs = [SystemMessage(content=sys_prompt)] + inputs

    try:
        result = agent.invoke({"messages": inputs}, config=config)
        return jsonify({"response": result["messages"][-1].content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('.', filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)