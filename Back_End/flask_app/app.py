from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os
from .schemas import UserCreate, Token, DocumentCreate, ChatMessage
from .utils import hash_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, pwd_context
from pydantic import ValidationError
from datetime import timedelta, datetime
from jose import jwt, JWTError
from werkzeug.utils import secure_filename
import openai
import PyPDF2
import requests
import json
import docx
import chromadb
from chromadb.config import Settings
import logging

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
client = MongoClient(MONGODB_URL)
db = client["customer_bot_db"]

# Initialize ChromaDB client and collection
chroma_client = chromadb.Client(Settings(persist_directory=os.path.join(os.path.dirname(__file__), '../chroma_db')))
doc_collection = chroma_client.get_or_create_collection("documents")

# Set up logging
logging.basicConfig(level=logging.INFO)

def scan_with_gpt(content: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Summarize the following document."},
            {"role": "user", "content": content}
        ],
        max_tokens=1024
    )
    return response.choices[0].message.content

def extract_text_from_pdf(file_stream):
    reader = PyPDF2.PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_docx(file_stream):
    doc = docx.Document(file_stream)
    return '\n'.join([para.text for para in doc.paragraphs])

def extract_text_from_url(url):
    try:
        resp = requests.get(url)
        if resp.headers.get('content-type', '').startswith('application/pdf'):
            from io import BytesIO
            return extract_text_from_pdf(BytesIO(resp.content))
        else:
            return resp.text[:5000]  # Limit for safety
    except Exception as e:
        return "Could not fetch or extract content from URL."

def save_processed_content_to_file(content, filename):
    folder = os.path.join(os.path.dirname(__file__), '../embeddings')
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def embed_text(text):
    response = openai.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def chunk_text(text, chunk_size=100, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    logging.info(f"Created {len(chunks)} chunks for document upload. Example chunk: {chunks[0] if chunks else 'None'}")
    return chunks

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        user = UserCreate(**data)
    except ValidationError as e:
        return jsonify({"detail": e.errors()}), 422

    if db.users.find_one({"email": user.email}) or db.users.find_one({"username": user.username}):
        return jsonify({"detail": "Email or username already registered"}), 400

    hashed_pw = hash_password(user.password)
    user_dict = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_pw,
    }
    result = db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)

    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(hours=24)
    )
    return jsonify({
        "access_token": access_token,
        "username": user.username,
        "email": user.email
    }), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"detail": "Email and password are required."}), 400
    user = db.users.find_one({"email": email})
    if not user or not pwd_context.verify(password, user.get("hashed_password", "")):
        return jsonify({"detail": "Invalid email or password."}), 401
    user_id = str(user["_id"])
    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(hours=24)
    )
    return jsonify({
        "access_token": access_token,
        "username": user["username"],
        "email": user["email"]
    }), 200

def get_current_user_id():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get('sub')
    except JWTError:
        return None

@app.route('/upload', methods=['POST'])
def upload_document():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401

    # Validation: limit to 3 documents per user
    user_doc_count = db.documents.count_documents({'user_id': user_id})
    if user_doc_count >= 3:
        return jsonify({'detail': 'You can only upload a maximum of 3 documents.'}), 400

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        file = request.files.get('file')
        doc_type = request.form.get('type')
        name = request.form.get('name') or (file.filename if file else None)
        if not file or not doc_type or doc_type not in ['pdf', 'doc', 'docx']:
            return jsonify({'detail': 'File and valid type (pdf/doc/docx) are required.'}), 400
        filename = secure_filename(file.filename)
        if doc_type == 'pdf':
            file.seek(0)
            file_content = extract_text_from_pdf(file)
        elif doc_type == 'docx' or (file.filename and file.filename.lower().endswith('.docx')):
            file.seek(0)
            file_content = extract_text_from_docx(file)
        else:
            file_content = file.read().decode('utf-8', errors='ignore')
        # Scan with GPT-4o-mini
        processed_content = scan_with_gpt(file_content[:5000])
        save_processed_content_to_file(processed_content, secure_filename(name) + '.txt')
        # Chunk and store embeddings
        chunks = chunk_text(processed_content)
        doc = {
            'user_id': user_id,
            'name': name,
            'type': doc_type,
            'content': processed_content,
            'uploaded_at': datetime.utcnow().isoformat(),
            'processed': True
        }
        result = db.documents.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        doc_id_str = doc['_id']
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id_str}_chunk_{idx}"
            embedding = embed_text(chunk)
            doc_collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"doc_id": doc_id_str, "user_id": user_id, "name": name, "chunk_index": idx}]
            )
        logging.info(f"Stored {len(chunks)} chunks in ChromaDB for doc_id {doc_id_str}")
        # Print all chunks stored in ChromaDB for this doc_id
        try:
            results = doc_collection.get(where={"doc_id": {"$eq": doc_id_str}})
            logging.info(f"Chunks in ChromaDB for doc_id {doc_id_str}: {results['documents']}")
        except Exception as e:
            logging.error(f"Error retrieving chunks from ChromaDB: {e}")
        return jsonify({"message": f"AI scanned your document: {name}", **doc}), 201
    else:
        try:
            data = request.json
            doc = DocumentCreate(**data)
        except ValidationError as e:
            return jsonify({'detail': e.errors()}), 422
        except Exception:
            return jsonify({'detail': 'Invalid request.'}), 400
        doc_dict = doc.dict()
        doc_dict['user_id'] = user_id
        doc_dict['uploaded_at'] = datetime.utcnow().isoformat()
        doc_dict['processed'] = True
        if doc_dict.get('url') is not None:
            doc_dict['url'] = str(doc_dict['url'])
            # Extract and scan content from URL
            url_content = extract_text_from_url(doc_dict['url'])
            doc_dict['content'] = scan_with_gpt(url_content[:5000])
            save_processed_content_to_file(doc_dict['content'], secure_filename(doc_dict['name']) + '.txt')
            # Chunk and store embeddings
            chunks = chunk_text(doc_dict['content'])
        result = db.documents.insert_one(doc_dict)
        doc_dict['_id'] = str(result.inserted_id)
        doc_id_str = doc_dict['_id']
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id_str}_chunk_{idx}"
            embedding = embed_text(chunk)
            doc_collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"doc_id": doc_id_str, "user_id": user_id, "name": doc_dict['name'], "chunk_index": idx}]
            )
        logging.info(f"Stored {len(chunks)} chunks in ChromaDB for doc_id {doc_id_str}")
        # Print all chunks stored in ChromaDB for this doc_id
        try:
            results = doc_collection.get(where={"doc_id": {"$eq": doc_id_str}})
            logging.info(f"Chunks in ChromaDB for doc_id {doc_id_str}: {results['documents']}")
        except Exception as e:
            logging.error(f"Error retrieving chunks from ChromaDB: {e}")
        return jsonify({"message": f"AI scanned your document: {doc_dict['name']}", **doc_dict}), 201

@app.route('/documents', methods=['GET'])
def get_documents():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    docs = list(db.documents.find({'user_id': user_id}))
    for doc in docs:
        doc['_id'] = str(doc['_id'])
    return jsonify(docs), 200

@app.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    result = db.documents.delete_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    db.chats.delete_many({'user_id': user_id, 'doc_id': doc_id})
    if result.deleted_count == 1:
        # Delete embedding file if it exists
        if doc and doc.get('name'):
            embedding_path = os.path.join(os.path.dirname(__file__), '../embeddings', secure_filename(doc['name']) + '.txt')
            try:
                if os.path.exists(embedding_path):
                    os.remove(embedding_path)
            except Exception:
                pass
        # Remove all chunks from ChromaDB
        try:
            doc_collection.delete(where={"doc_id": doc_id, "user_id": user_id})
        except Exception:
            pass
        return jsonify({'message': 'Document, related chats, and embedding file deleted successfully.'}), 200
    else:
        return jsonify({'detail': 'Document not found or not authorized.'}), 404

@app.route('/chat', methods=['POST'])
def chat_with_doc():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401

    data = request.json
    doc_id = data.get('doc_id')
    question = data.get('question')
    
    if not doc_id or not question:
        return jsonify({'detail': 'doc_id and question are required.'}), 400

    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    if not doc:
        return jsonify({'detail': 'Document not found or not authorized.'}), 404

    context = doc.get('content', '')

    # Always use the strict document-only prompt
    prompt = (
        "You are a helpful assistant. Use ONLY the following document content to answer the user's question. "
        "If you cannot find the answer in the document, reply with exactly: 'The answer is not present in the document.' "
        "Do not use any outside knowledge.\n\n"
        f"Document Content:\n{context}\n\nQuestion: {question}"
    )
    answer = scan_with_gpt(prompt)
    # Post-processing: enforce strict document-only answers
    # if answer.strip().lower() != "the answer is not present in the document.":
    #     if answer not in context:
    #         answer = "The answer is not present in the document."

    # Store chat history
    chat_msg = ChatMessage(
        user_id=user_id,
        doc_id=doc_id,
        question=question,
        answer=answer,
        timestamp=datetime.utcnow().isoformat()
    )
    db.chats.insert_one(chat_msg.dict())

    return jsonify({'answer': answer}), 200

@app.route('/chat', methods=['GET'])
def get_chat_history():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    doc_id = request.args.get('doc_id')
    if not doc_id:
        return jsonify({'detail': 'doc_id is required as a query parameter.'}), 400
    chats = list(db.chats.find({'user_id': user_id, 'doc_id': doc_id}))
    for chat in chats:
        chat['_id'] = str(chat['_id'])
    return jsonify(chats), 200

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return jsonify({"detail": str(e), "trace": traceback.format_exc()}), 500

if __name__ == "__main__":
    app.run(debug=True) 