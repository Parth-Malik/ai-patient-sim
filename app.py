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
# Support multiple keys for rotation or single key
keys_env = os.getenv("GROQ_API_KEYS")
api_keys = [k.strip() for k in keys_env.split(',')] if keys_env else ["dummy_key"]

# DB SETUP
mongo_uri = os.getenv("MONGO_URI")
secret_key = os.getenv("SECRET_KEY", "super_secret_key")

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# --- HYBRID DATABASE LOGIC ---
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
        db_client.server_info() # Trigger connection check
        print("✅ CONNECTED TO MONGODB ATLAS")
        
        db = db_client.medsim_db
        users_col = db.users
        sessions_col = db.sessions
        use_mongo = True
    except ServerSelectionTimeoutError:
        print("⚠️ MONGODB CONNECTION FAILED. Falling back to In-Memory mode.")
        use_mongo = False
else:
    print("⚠️ NO MONGO_URI FOUND. Using In-Memory mode.")
    use_mongo = False


# --- AUTH ROUTES ---

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
        
        new_user = {
            "_id": "user_" + str(len(ram_db["users"])),
            "username": username,
            "password": hashed_pw
        }
        ram_db["users"].append(new_user)
        return jsonify({"message": "User created (RAM)", "user_id": new_user["_id"]}), 201

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


# --- HELPER FUNCTIONS ---

def get_llm(temp=0.7):
    return ChatGroq(
        api_key=random.choice(api_keys), 
        model="llama-3.1-8b-instant", 
        temperature=temp
    )

def parse_json(text):
    text = re.sub(r'```json\s*|```', '', text).strip()
    start, end = text.find('{'), text.rfind('}') + 1
    if start != -1 and end != -1:
        return json.loads(text[start:end])
    return {}

# --- CREATOR AGENT ---

def generate_patient():
    print("🧬 Generating FRESH patient case...")
    llm = get_llm(1.0) 
    prompt = """
    Create a realistic medical patient profile.
    RULES: Avoid common colds. Pick distinct conditions (e.g., IBS, Migraine, Eczema, Sciatica).
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
        p = parse_json(llm.invoke(prompt).content)
        if isinstance(p.get('visible_symptoms'), str): 
            p['visible_symptoms'] = [p['visible_symptoms']]
        return p
    except:
        return {
            "name": "Alex", "age": 30, "sex": "Male", 
            "disease": "Migraine", 
            "visible_symptoms": ["Headache", "Light sensitivity"], 
            "secret_symptom": "Nausea", 
            "pain_description": "Throbbing", 
            "treatment": ["Triptans"]
        }

def get_system_prompt(p):
    """
    STRICT NO-DRAMA PROMPT
    This ensures the bot speaks like a normal person texting, not an actor.
    """
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
    
    === STRICT BEHAVIOR RULES ===
    1. NO ACTING: Do NOT use asterisks (*sigh*, *looks down*). Do NOT describe your actions. Just type words.
    2. TEXTING STYLE: Keep sentences short and casual.
    3. NO INFO DUMPING: Only mention your Main Symptom at first. Make the doctor ask for more.
       - BAD: "Hi, I have a headache, nausea, and my eye hurts."
       - GOOD: "Hi doc, I've had this really bad headache all day."
    4. UNKNOWN: If asked about history not in your profile, say "No" or "I don't think so."
    
    Start now. Wait for the doctor to speak.
    """


# --- ACTOR AGENT ---

class State(TypedDict):
    messages: Annotated[List, operator.add]

def bot_node(state: State):
    try:
        # Lower temp (0.4) reduces chance of "hallucinating" drama
        return {"messages": [get_llm(0.4).invoke(state["messages"])]}
    except:
        return {"messages": [HumanMessage(content="...")]}

workflow = StateGraph(State)
workflow.add_node("patient", bot_node)
workflow.set_entry_point("patient")
workflow.add_edge("patient", END)
memory = MemorySaver()
agent = workflow.compile(checkpointer=memory)


# --- CHAT ROUTES ---

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
    
    if not session:
        # Create new session
        p = generate_patient()
        new_session = {
            "thread_id": tid, 
            "user_id": uid, 
            "patient_name": p['name'], 
            "disease": p['disease'],
            "patient_data": p, 
            "messages": [], 
            "created_at": datetime.datetime.now()
        }
        
        if use_mongo:
            sessions_col.insert_one(new_session)
        else:
            ram_db["sessions"].append(new_session)
            
        inputs = [SystemMessage(content=get_system_prompt(p)), HumanMessage(content=msg)]
        current_p = p
    else:
        # Continue session
        current_p = session['patient_data']
        inputs = [HumanMessage(content=msg)]

    try:
        res = agent.invoke({"messages": inputs}, config=config)
        bot_response = res["messages"][-1].content
        
        # Save history
        new_msgs = [
            {"role": "Doctor", "content": msg},
            {"role": "Patient", "content": bot_response}
        ]
        
        if use_mongo:
            sessions_col.update_one(
                {"thread_id": tid},
                {"$push": {"messages": {"$each": new_msgs}}}
            )
        else:
            for s in ram_db["sessions"]:
                if s["thread_id"] == tid:
                    s["messages"].extend(new_msgs)
                    break
                    
        return jsonify({
            "response": bot_response,
            "patient_info": {
                "name": current_p["name"], 
                "age": current_p["age"], 
                "sex": current_p["sex"]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<user_id>', methods=['GET'])
def get_sessions(user_id):
    results = []
    
    if use_mongo:
        cursor = sessions_col.find({"user_id": user_id}).sort("created_at", -1)
        for doc in cursor:
            results.append({
                "thread_id": doc["thread_id"], 
                "patient": doc["patient_name"], 
                "disease": doc["disease"]
            })
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
