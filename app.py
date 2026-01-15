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

# LangChain imports
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Annotated
import operator

# Load env vars
load_dotenv()

# Setup Groq keys - supports rotation
keys_env = os.getenv("GROQ_API_KEYS")
api_keys = [k.strip() for k in keys_env.split(',')] if keys_env else ["dummy_key"]

# Database config
mongo_uri = os.getenv("MONGO_URI")
secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# Database connection logic
use_mongo = False
db_client = None
users_col = None
sessions_col = None

# RAM fallback
ram_db = {
    "users": [],
    "sessions": []
}

if mongo_uri:
    try:
        db_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        db_client.server_info() 
        print("Connected to MongoDB Atlas")
        
        db = db_client.medsim_db
        users_col = db.users
        sessions_col = db.sessions
        use_mongo = True
    except ServerSelectionTimeoutError:
        print("MongoDB connection failed. Switching to RAM mode.")
        use_mongo = False
else:
    print("No Mongo URI found. Switching to RAM mode.")
    use_mongo = False


# --- Auth Routes ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400
    
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    
    if use_mongo:
        if users_col.find_one({"username": username}):
            return jsonify({"error": "User already exists"}), 400
        
        uid = users_col.insert_one({
            "username": username, 
            "password": hashed_pw, 
            "created_at": datetime.datetime.now()
        }).inserted_id
        
        return jsonify({"message": "User created", "user_id": str(uid)}), 201
    else:
        for u in ram_db["users"]:
            if u["username"] == username:
                return jsonify({"error": "User already exists"}), 400
        
        new_id = f"user_{len(ram_db['users'])}"
        new_user = {"_id": new_id, "username": username, "password": hashed_pw}
        ram_db["users"].append(new_user)
        return jsonify({"message": "User created (RAM)", "user_id": new_id}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = None
    if use_mongo:
        user = users_col.find_one({"username": username})
    else:
        for u in ram_db["users"]:
            if u["username"] == username:
                user = u
                break
    
    if user and bcrypt.check_password_hash(user['password'], password):
        uid = str(user['_id'])
        token = jwt.encode({
            'user_id': uid,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, secret_key, algorithm="HS256")
        
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user_id": uid,
            "username": user['username']
        })
    
    return jsonify({"error": "Invalid credentials"}), 401


# --- Helper Functions ---

def get_llm(temp=0.7):
    selected_key = random.choice(api_keys)
    return ChatGroq(
        api_key=selected_key, 
        model="llama-3.1-8b-instant", 
        temperature=temp
    )

def clean_json_output(text):
    text = re.sub(r'```json\s*|```', '', text).strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}') + 1
    if start_idx != -1 and end_idx != -1:
        return json.loads(text[start_idx:end_idx])
    return {}


# --- Patient Generation ---

def create_patient_profile():
    print("Generating new patient profile...")
    llm = get_llm(1.0) 
    
    prompt = """
    Create a realistic medical patient profile.
    Avoid common colds. Pick distinct conditions (e.g., IBS, Migraine, Eczema, Sciatica, STI).
    
    Return ONLY valid JSON:
    {
        "name": "First Name",
        "age": Integer,
        "sex": "Male/Female",
        "disease": "Specific Condition",
        "visible_symptoms": ["Main Symptom", "Secondary Symptom", "Tertiary Symptom"],
        "secret_symptom": "Critical clue (only reveal if specifically asked)",
        "pain_description": "Sensory adjectives (e.g. sharp, burning)",
        "treatment": ["Correct Meds"]
    }
    """
    
    try:
        response = llm.invoke(prompt).content
        profile = clean_json_output(response)
        if isinstance(profile.get('visible_symptoms'), str):
            profile['visible_symptoms'] = [profile['visible_symptoms']]
        return profile
    except Exception as e:
        # Fallback profile
        return {
            "name": "Alex", "age": 30, "sex": "Male", 
            "disease": "Migraine", 
            "visible_symptoms": ["Headache", "Light sensitivity"], 
            "secret_symptom": "Nausea", 
            "pain_description": "Throbbing", 
            "treatment": ["Triptans"]
        }

def build_system_prompt(p):
    # STRICT TEXTING STYLE PROMPT
    return f"""
    ROLE: You are {p['name']}, {p['age']} years old, {p['sex']}.
    CONTEXT: You are messaging a doctor on a chat app.
    
    === YOUR CONDITION ===
    Disease: {p['disease']} (NEVER reveal this name).
    Main Symptom: {p['visible_symptoms'][0]}.
    Other Symptoms: {", ".join(p['visible_symptoms'][1:])}.
    Secret: {p['secret_symptom']} (Only say if explicitly asked).
    Pain feels like: {p.get('pain_description', 'bad')}.
    
    === THE CURE ===
    The ONLY thing that helps is: {', '.join(p['treatment'])}.
    IF the doctor suggests this:
    1. Say: "Okay, I'll try that." or "Thanks doc."
    2. STOP complaining.
    
    === STRICT BEHAVIOR RULES (CRITICAL) ===
    1. NO ACTING: Do NOT use asterisks (*sigh*, *looks down*). Do NOT describe your physical actions. 
    2. TEXTING STYLE: Type like a normal person texting. Short sentences. Casual.
    3. ONE THING AT A TIME: Do NOT list all your symptoms at once.
       - BAD: "Hi, I have a headache, nausea, and my eye hurts."
       - GOOD: "Hi doc, I've had this really bad headache all day."
    4. WAIT FOR QUESTIONS: Only reveal secondary symptoms if the doctor asks "Anything else?" or "Does it hurt anywhere else?"
    5. UNKNOWN: If asked about history not in your profile, say "No" or "I don't think so."
    
    Start now. Wait for the doctor to speak.
    """


# --- Chat Logic ---

class AgentState(TypedDict):
    messages: Annotated[List, operator.add]

def bot_response_node(state: AgentState):
    try:
        # Use low temp (0.3) to prevent "creative" acting/drama
        llm = get_llm(0.3)
        response = llm.invoke(state["messages"])
        return {"messages": [response]}
    except:
        return {"messages": [HumanMessage(content="...")]}

workflow = StateGraph(AgentState)
workflow.add_node("patient", bot_response_node)
workflow.set_entry_point("patient")
workflow.add_edge("patient", END)

memory = MemorySaver()
agent = workflow.compile(checkpointer=memory)


# --- Routes ---

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    uid = data.get('user_id')
    tid = data.get('thread_id')
    msg = data.get('message')
    
    if not all([uid, tid, msg]):
        return jsonify({"error": "Bad Request"}), 400
    
    config = {"configurable": {"thread_id": tid}}
    
    # Retrieve session
    session = None
    if use_mongo:
        session = sessions_col.find_one({"thread_id": tid})
    else:
        for s in ram_db["sessions"]:
            if s["thread_id"] == tid:
                session = s
                break
    
    # New Session Logic
    if not session:
        profile = create_patient_profile()
        new_session = {
            "thread_id": tid, 
            "user_id": uid, 
            "patient_name": profile['name'], 
            "disease": profile['disease'], 
            "patient_data": profile, 
            "messages": [], 
            "created_at": datetime.datetime.now()
        }
        
        if use_mongo:
            sessions_col.insert_one(new_session)
        else:
            ram_db["sessions"].append(new_session)
            
        # Seed conversation
        inputs = [
            SystemMessage(content=build_system_prompt(profile)), 
            HumanMessage(content=msg)
        ]
        current_profile = profile
    else:
        # Continue session
        current_profile = session['patient_data']
        inputs = [HumanMessage(content=msg)]

    try:
        result = agent.invoke({"messages": inputs}, config=config)
        bot_text = result["messages"][-1].content
        
        # Save history
        new_messages = [
            {"role": "Doctor", "content": msg}, 
            {"role": "Patient", "content": bot_text}
        ]
        
        if use_mongo:
            sessions_col.update_one(
                {"thread_id": tid}, 
                {"$push": {"messages": {"$each": new_messages}}}
            )
        else:
            for s in ram_db["sessions"]:
                if s["thread_id"] == tid:
                    s["messages"].extend(new_messages)
                    break
                    
        return jsonify({
            "response": bot_text, 
            "patient_info": {
                "name": current_profile["name"], 
                "age": current_profile["age"], 
                "sex": current_profile["sex"]
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@app.route('/sessions/<user_id>', methods=['GET'])
def get_sessions(user_id):
    results = []
    
    if use_mongo:
        cursor = sessions_col.find({"user_id": user_id}).sort("created_at", -1)
        results = [
            {"thread_id": doc["thread_id"], "patient": doc["patient_name"], "disease": doc["disease"]} 
            for doc in cursor
        ]
    else:
        for s in reversed(ram_db["sessions"]):
            if s["user_id"] == user_id:
                results.append({
                    "thread_id": s["thread_id"], 
                    "patient": s["patient_name"], 
                    "disease": s["disease"]
                })
                
    return jsonify(results)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:f>')
def static_files(f):
    return send_from_directory('.', f)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
