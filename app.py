import os
import random
import json
import re
import jwt
import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# --- LANGCHAIN IMPORTS ---
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Annotated
import operator

# --- CONFIGURATION ---
load_dotenv()
keys = os.getenv("GROQ_API_KEYS")
API_KEYS = [k.strip() for k in keys.split(',')] if keys else ["dummy"]

# DB SETUP
MONGO_URI = None
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# --- HYBRID DATABASE LOGIC ---
# We try to connect to Mongo. If it fails, we fall back to a Python Dictionary.
USE_MONGO = False
db_client = None
users_col = None
sessions_col = None

# In-Memory Fallback
RAM_DB = {
    "users": [],
    "sessions": []
}

if MONGO_URI:
    try:
        db_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) # 5s timeout
        # Test connection
        db_client.server_info()
        print("✅ CONNECTED TO MONGODB ATLAS")
        db = db_client.medsim_db
        users_col = db.users
        sessions_col = db.sessions
        USE_MONGO = True
    except ServerSelectionTimeoutError:
        print("⚠️ MONGODB CONNECTION FAILED. Falling back to In-Memory mode.")
        USE_MONGO = False
else:
    print("⚠️ NO MONGO_URI FOUND. Using In-Memory mode.")
    USE_MONGO = False

# --- AUTH ROUTES ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400
    
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    
    if USE_MONGO:
        if users_col.find_one({"username": username}):
            return jsonify({"error": "User already exists"}), 400
        
        uid = users_col.insert_one({
            "username": username, "password": hashed_pw, "created_at": datetime.datetime.now()
        }).inserted_id
        return jsonify({"message": "User created", "user_id": str(uid)}), 201
    else:
        # RAM Fallback
        for u in RAM_DB["users"]:
            if u["username"] == username:
                return jsonify({"error": "User already exists"}), 400
        
        new_user = {
            "_id": "user_" + str(len(RAM_DB["users"])),
            "username": username,
            "password": hashed_pw
        }
        RAM_DB["users"].append(new_user)
        return jsonify({"message": "User created (RAM)", "user_id": new_user["_id"]}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = None
    
    if USE_MONGO:
        user = users_col.find_one({"username": username})
    else:
        # RAM Fallback
        for u in RAM_DB["users"]:
            if u["username"] == username:
                user = u
                break
    
    if user and bcrypt.check_password_hash(user['password'], password):
        # Determine User ID (Mongo uses ObjectId, RAM uses string)
        uid = str(user['_id'])
        token = jwt.encode({
            'user_id': uid,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, algorithm="HS256")
        
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user_id": uid,
            "username": user['username']
        })
    
    return jsonify({"error": "Invalid credentials"}), 401

# --- HELPER FUNCTIONS ---
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

# --- CREATOR AGENT ---
def generate_patient():
    print("🧬 Generating FRESH patient case...")
    llm = get_llm(1.0) 
    prompt = """
    Create a realistic medical patient profile.
    RULES: Avoid colds/flu. Pick distinct conditions (e.g. GERD, Migraine).
    Return ONLY valid JSON:
    {
        "name": "First Name",
        "age": Integer,
        "sex": "Male/Female",
        "disease": "Specific Condition",
        "visible_symptoms": ["Main Symptom", "Secondary Symptom"],
        "secret_symptom": "Critical clue",
        "pain_description": "Sensory adjectives",
        "speech_style": "Natural/Casual",
        "treatment": ["Correct Meds"]
    }
    """
    try:
        p = parse_json(llm.invoke(prompt).content)
        if isinstance(p.get('visible_symptoms'), str): p['visible_symptoms'] = [p['visible_symptoms']]
        return p
    except:
        return {"name": "Alex", "age": 30, "sex": "Male", "disease": "Headache", "visible_symptoms": ["Pain"], "secret_symptom": "Stress", "pain_description": "Throbbing", "speech_style": "Tired", "treatment": ["Rest"]}

def get_system_prompt(p):
    return f"""
    ROLE: You are {p['name']}, {p['age']} years old, {p['sex']}.
    REALITY: Condition {p['disease']} (NEVER say name). Symptoms: {", ".join(p['visible_symptoms'])}.
    PAIN: {p.get('pain_description', 'bad')}. SECRET: {p['secret_symptom']}.
    CURE: {', '.join(p['treatment'])}. Accept if offered.
    STYLE: Descriptive, natural, sensory details.
    """

# --- ACTOR AGENT ---
class State(TypedDict):
    messages: Annotated[List, operator.add]

def bot_node(state: State):
    try:
        return {"messages": [get_llm(0.6).invoke(state["messages"])]}
    except:
        return {"messages": [HumanMessage(content="...")]}

workflow = StateGraph(State)
workflow.add_node("patient", bot_node)
workflow.set_entry_point("patient")
workflow.add_edge("patient", END)
memory = MemorySaver()
agent = workflow.compile(checkpointer=memory)

# --- 6. CHAT ROUTES ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    uid = data.get('user_id')
    tid = data.get('thread_id')
    msg = data.get('message')
    
    if not uid or not tid or not msg: return jsonify({"error": "Bad Request"}), 400
    
    config = {"configurable": {"thread_id": tid}}
    
    # --- GET OR CREATE SESSION ---
    session = None
    if USE_MONGO:
        session = sessions_col.find_one({"thread_id": tid})
    else:
        # RAM Fallback
        for s in RAM_DB["sessions"]:
            if s["thread_id"] == tid:
                session = s
                break
    
    if not session:
        # New Session
        p = generate_patient()
        new_session = {
            "thread_id": tid, "user_id": uid, 
            "patient_name": p['name'], "disease": p['disease'],
            "patient_data": p, "messages": [], "created_at": datetime.datetime.now()
        }
        
        if USE_MONGO:
            sessions_col.insert_one(new_session)
        else:
            RAM_DB["sessions"].append(new_session)
            
        inputs = [SystemMessage(content=get_system_prompt(p)), HumanMessage(content=msg)]
        current_p = p
    else:
        # Existing Session
        current_p = session['patient_data']
        inputs = [HumanMessage(content=msg)]

    # --- RUN AGENT ---
    try:
        res = agent.invoke({"messages": inputs}, config=config)
        bot_response = res["messages"][-1].content
        
        # --- SAVE HISTORY ---
        new_msgs = [
            {"role": "Doctor", "content": msg},
            {"role": "Patient", "content": bot_response}
        ]
        
        if USE_MONGO:
            sessions_col.update_one(
                {"thread_id": tid},
                {"$push": {"messages": {"$each": new_msgs}}}
            )
        else:
            # RAM Update
            for s in RAM_DB["sessions"]:
                if s["thread_id"] == tid:
                    s["messages"].extend(new_msgs)
                    break
                    
        return jsonify({
            "response": bot_response,
            "patient_info": {"name": current_p["name"], "age": current_p["age"], "sex": current_p["sex"]}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<user_id>', methods=['GET'])
def get_sessions(user_id):
    results = []
    
    if USE_MONGO:
        cursor = sessions_col.find({"user_id": user_id}).sort("created_at", -1)
        for doc in cursor:
            results.append({
                "thread_id": doc["thread_id"], 
                "patient": doc["patient_name"], 
                "disease": doc["disease"]
            })
    else:
        # RAM Fallback
        for s in reversed(RAM_DB["sessions"]):
            if s["user_id"] == user_id:
                results.append({
                    "thread_id": s["thread_id"],
                    "patient": s["patient_name"],
                    "disease": s["disease"]
                })
                
    return jsonify(results)

@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/<path:f>')
def static_files(f): return send_from_directory('.', f)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
