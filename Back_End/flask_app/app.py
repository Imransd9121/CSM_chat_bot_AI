from flask import Flask, request, jsonify, send_file
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
from docx import Document
import chromadb
from chromadb.config import Settings
import logging
import re
import certifi
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
from bs4 import BeautifulSoup
from gtts import gTTS
import io
from google.cloud import texttospeech
import tempfile
import pyttsx3
import wave
import contextlib
import soundfile as sf
# Remove pydub import and all AudioSegment usage for Python 3.13 compatibility

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where())
db = client["customer_bot_db"]

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

try:
    # The ismaster command is cheap and does not require auth.
    client.admin.command('ismaster')
    print("[INFO] Database connected successfully.")
except Exception as e:
    print(f"[ERROR] Database connection failed: {e}")

# Initialize ChromaDB client and collection
chroma_client = chromadb.Client(Settings(persist_directory=os.path.join(os.path.dirname(__file__), '../chroma_db')))
doc_collection = chroma_client.get_or_create_collection("documents")

# Set up logging
logging.basicConfig(level=logging.INFO)

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_email(to_email, subject, body):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USERNAME, to_email, text)
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Email sending failed: {e}")
        return False

def scan_with_gpt(content: str) -> str:
    print("=== PROMPT SENT TO MODEL ===")
    print(content)
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
        page_text = page.extract_text() or ""
        # Clean up the extracted text
        page_text = re.sub(r'\s+', ' ', page_text)  # Remove extra whitespace
        page_text = page_text.strip()
        if page_text:
            text += page_text + "\n\n"
    return text.strip()

def extract_text_from_docx(file_stream):
    doc = Document(file_stream)
    text_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text.strip())
    return '\n\n'.join(text_parts)

def extract_text_from_url(url):
    try:
        resp = requests.get(url, timeout=30)
        if resp.headers.get('content-type', '').startswith('application/pdf'):
            from io import BytesIO
            return extract_text_from_pdf(BytesIO(resp.content))
        else:
            # For HTML content, try to extract meaningful text
            soup = BeautifulSoup(resp.content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text[:10000]  # Increased limit for large documents
    except Exception as e:
        return f"Could not fetch or extract content from URL: {str(e)}"

def save_processed_content_to_file(content, filename):
    folder = os.path.join(os.path.dirname(__file__), '../embeddings')
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def embed_text(text):
    try:
        response = openai.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Embedding error: {e}")
        return None

def chunk_text(text, chunk_size=500, overlap=100):
    """
    Improved chunking strategy for large documents.
    - Larger chunk size (500 words) for better context
    - Smaller overlap (100 words) to reduce redundancy
    - Better text cleaning and processing
    - Improved sentence boundary detection
    """
    # Clean the text first
    text = re.sub(r'\s+', ' ', text)  # Remove extra whitespace
    text = text.strip()
    
    if not text:
        return []
    
    # Split into sentences first for better boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_words = sentence.split()
        sentence_word_count = len(sentence_words)
        
        # If adding this sentence would exceed chunk size
        if current_word_count + sentence_word_count > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text.strip()) > 50:  # Only add chunks with meaningful content
                chunks.append(chunk_text.strip())
            
            # Start new chunk with overlap
            overlap_words = []
            if overlap > 0:
                # Take last few sentences for overlap
                for sent in reversed(current_chunk):
                    sent_words = sent.split()
                    if len(overlap_words) + len(sent_words) <= overlap:
                        overlap_words = sent_words + overlap_words
                    else:
                        break
            
            current_chunk = overlap_words + [sentence]
            current_word_count = len(overlap_words) + sentence_word_count
        else:
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_word_count += sentence_word_count
    
    # Add the last chunk if it exists
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if len(chunk_text.strip()) > 50:
            chunks.append(chunk_text.strip())
    
    # If we have too few chunks, try paragraph-based chunking
    if len(chunks) < 2:
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            para_words = paragraph.split()
            para_word_count = len(para_words)
            
            if current_word_count + para_word_count > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text.strip()) > 50:
                    chunks.append(chunk_text.strip())
                
                # Start new chunk with overlap
                overlap_words = []
                if overlap > 0:
                    for para in reversed(current_chunk):
                        para_words = para.split()
                        if len(overlap_words) + len(para_words) <= overlap:
                            overlap_words = para_words + overlap_words
                        else:
                            break
                
                current_chunk = overlap_words + [paragraph]
                current_word_count = len(overlap_words) + para_word_count
            else:
                current_chunk.append(paragraph)
                current_word_count += para_word_count
        
        # Add the last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text.strip()) > 50:
                chunks.append(chunk_text.strip())
    
    logging.info(f"Created {len(chunks)} chunks for document upload. Total words: {len(text.split())}")
    if chunks:
        logging.info(f"First chunk preview: {chunks[0][:200]}...")
    
    return chunks

def process_large_document(content, max_chunks=30):
    """
    Process large documents with intelligent chunking and summarization.
    More conservative approach for very large documents.
    """
    # If content is extremely large, create a summary first
    if len(content.split()) > 20000:  # More than 20k words
        logging.info("Document is extremely large, creating comprehensive summary first...")
        try:
            summary_prompt = f"""
            Please provide a comprehensive summary of the following document, 
            preserving all important information, key points, and details that 
            would be needed to answer questions about the content. 
            Focus on factual information, procedures, definitions, and important concepts.
            Make the summary detailed but concise.
            
            Document content:
            {content[:20000]}  # Use first 20k words for summary
            """
            
            summary = scan_with_gpt(summary_prompt)
            logging.info(f"Created summary of {len(summary)} characters")
            
            # Use the summary for chunking with larger chunks
            chunks = chunk_text(summary, chunk_size=1000, overlap=200)
        except Exception as e:
            logging.error(f"Summary creation failed: {e}")
            # Fallback to original content with smaller chunks
            chunks = chunk_text(content, chunk_size=300, overlap=50)
    elif len(content.split()) > 10000:  # More than 10k words
        logging.info("Document is very large, creating summary first...")
        try:
            summary_prompt = f"""
            Please provide a comprehensive summary of the following document, 
            preserving all important information, key points, and details that 
            would be needed to answer questions about the content. 
            Focus on factual information, procedures, definitions, and important concepts.
            
            Document content:
            {content[:15000]}  # Use first 15k words for summary
            """
            
            summary = scan_with_gpt(summary_prompt)
            logging.info(f"Created summary of {len(summary)} characters")
            
            # Use the summary for chunking
            chunks = chunk_text(summary, chunk_size=800, overlap=150)
        except Exception as e:
            logging.error(f"Summary creation failed: {e}")
            # Fallback to original content
            chunks = chunk_text(content, chunk_size=500, overlap=100)
    else:
        # For smaller documents, use regular chunking
        chunks = chunk_text(content, chunk_size=500, overlap=100)
    
    # Limit the number of chunks to prevent overwhelming the system
    if len(chunks) > max_chunks:
        logging.info(f"Limiting chunks from {len(chunks)} to {max_chunks}")
        chunks = chunks[:max_chunks]
    
    return chunks

# def transcribe_audio(file_stream):
#     """
#     Transcribe audio using OpenAI Whisper API.
#     Accepts a file-like object and returns the transcribed text.
#     """
#     response = openai.audio.transcriptions.create(
#         model="whisper-1",
#         file=file_stream
#     )
#     return response.text

def estimate_tokens(text):
    """
    Rough estimation of tokens (1 token ≈ 4 characters for English text)
    This is a conservative estimate to stay within limits
    """
    return len(text) // 4

def truncate_content_for_model(content, max_tokens=100000):
    """
    Truncate content to fit within model's token limit
    Preserves the most important parts (beginning and end)
    """
    estimated_tokens = estimate_tokens(content)
    
    if estimated_tokens <= max_tokens:
        return content
    
    # Calculate how much to keep from beginning and end
    chars_per_token = 4
    max_chars = max_tokens * chars_per_token
    
    # Keep 60% from beginning, 40% from end
    beginning_chars = int(max_chars * 0.6)
    end_chars = int(max_chars * 0.4)
    
    beginning = content[:beginning_chars]
    end = content[-end_chars:] if len(content) > beginning_chars else ""
    
    # Find a good break point near the middle
    middle_start = beginning_chars - 1000
    middle_end = beginning_chars + 1000
    
    # Look for paragraph breaks or sentence breaks
    break_point = beginning.rfind('\n\n')
    if break_point == -1:
        break_point = beginning.rfind('. ')
    if break_point == -1:
        break_point = beginning.rfind(' ')
    
    if break_point > middle_start and break_point < middle_end:
        beginning = content[:break_point]
    
    truncated_content = beginning + "\n\n[Content truncated due to length. Showing most relevant sections.]\n\n" + end
    
    logging.info(f"Content truncated from {estimated_tokens} tokens to approximately {estimate_tokens(truncated_content)} tokens")
    return truncated_content

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

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json
    email = data.get("email")
    
    if not email:
        return jsonify({"detail": "Email is required."}), 400
    
    # Check if user exists
    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"detail": "If an account with this email exists, you will receive a password reset link."}), 200
    
    # Generate OTP
    otp = generate_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)  # OTP expires in 10 minutes
    
    # Store OTP in database
    db.password_resets.update_one(
        {"email": email},
        {
            "$set": {
                "otp": otp,
                "expires_at": otp_expiry,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )
    
    # Send email with OTP
    subject = "Password Reset OTP - AI Assistant"
    body = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>You have requested to reset your password for your AI Assistant account.</p>
        <p>Your OTP is: <strong style="font-size: 24px; color: #2563eb;">{otp}</strong></p>
        <p>This OTP will expire in 10 minutes.</p>
        <p>If you didn't request this password reset, please ignore this email.</p>
        <br>
        <p>Best regards,<br>AI Assistant Team</p>
    </body>
    </html>
    """
    
    if send_email(email, subject, body):
        return jsonify({"message": "If an account with this email exists, you will receive a password reset OTP."}), 200
    else:
        return jsonify({"detail": "Failed to send email. Please try again later."}), 500

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")
    
    if not email or not otp:
        return jsonify({"detail": "Email and OTP are required."}), 400
    
    # Check if OTP exists and is valid
    reset_data = db.password_resets.find_one({"email": email})
    if not reset_data:
        return jsonify({"detail": "Invalid OTP or email."}), 400
    
    # Check if OTP is expired
    if datetime.utcnow() > reset_data["expires_at"]:
        db.password_resets.delete_one({"email": email})
        return jsonify({"detail": "OTP has expired. Please request a new one."}), 400
    
    # Check if OTP matches
    if reset_data["otp"] != otp:
        return jsonify({"detail": "Invalid OTP."}), 400
    
    # Generate a temporary token for password reset
    temp_token = create_access_token(
        data={"sub": email, "type": "password_reset"},
        expires_delta=timedelta(minutes=15)
    )
    
    # Delete the used OTP
    db.password_resets.delete_one({"email": email})
    
    return jsonify({
        "message": "OTP verified successfully.",
        "reset_token": temp_token
    }), 200

@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    reset_token = data.get("reset_token")
    new_password = data.get("new_password")
    
    if not reset_token or not new_password:
        return jsonify({"detail": "Reset token and new password are required."}), 400
    
    try:
        # Verify the reset token
        payload = jwt.decode(reset_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if not email or token_type != "password_reset":
            return jsonify({"detail": "Invalid reset token."}), 400
        
        # Check if user exists
        user = db.users.find_one({"email": email})
        if not user:
            return jsonify({"detail": "User not found."}), 404
        
        # Hash the new password
        hashed_password = hash_password(new_password)
        
        # Update user's password
        db.users.update_one(
            {"email": email},
            {"$set": {"hashed_password": hashed_password}}
        )
        
        return jsonify({"message": "Password reset successfully."}), 200
        
    except JWTError:
        return jsonify({"detail": "Invalid or expired reset token."}), 400

@app.route("/delete-user", methods=["DELETE"])
def delete_user():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"detail": "Authentication required."}), 401
    
    # Verify user exists
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"detail": "User not found."}), 404
    
    try:
        # Delete user's documents and related data
        user_docs = list(db.documents.find({"user_id": user_id}))
        for doc in user_docs:
            doc_id = str(doc["_id"])
            # Delete document embeddings from ChromaDB
            try:
                doc_collection.delete(where={"doc_id": doc_id, "user_id": user_id})
            except Exception:
                pass
            # Delete embedding files
            if doc.get('name'):
                embedding_path = os.path.join(os.path.dirname(__file__), '../embeddings', secure_filename(doc['name']) + '.txt')
                try:
                    if os.path.exists(embedding_path):
                        os.remove(embedding_path)
                except Exception:
                    pass
        
        # Delete all user data
        db.documents.delete_many({"user_id": user_id})
        db.chats.delete_many({"user_id": user_id})
        db.users.delete_one({"_id": ObjectId(user_id)})
        
        return jsonify({"message": "User account and all associated data deleted successfully."}), 200
    except Exception as e:
        return jsonify({"detail": f"Error deleting user: {str(e)}"}), 500

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
        
        # Extract text from file
        if doc_type == 'pdf':
            file.seek(0)
            file_content = extract_text_from_pdf(file)
        elif doc_type == 'docx' or (file.filename and file.filename.lower().endswith('.docx')):
            file.seek(0)
            file_content = extract_text_from_docx(file)
        else:
            file_content = file.read().decode('utf-8', errors='ignore')
        
        # Check if content is extracted successfully
        if not file_content or len(file_content.strip()) < 50:
            return jsonify({'detail': 'Could not extract meaningful content from the file. Please ensure the file contains readable text.'}), 400
        
        logging.info(f"Extracted {len(file_content)} characters from document")
        
        # Use improved document processing for large files
        chunks = process_large_document(file_content)
        
        if not chunks:
            return jsonify({'detail': 'Could not process the document content. Please try a different file.'}), 400
        
        # Store the original content for chat context
        doc = {
            'user_id': user_id,
            'name': name,
            'type': doc_type,
            'content': file_content,  # Store original content
            'uploaded_at': datetime.utcnow().isoformat() + 'Z',
            'processed': True
        }
        result = db.documents.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        doc_id_str = doc['_id']
        
        # Store embeddings for each chunk
        successful_embeddings = 0
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id_str}_chunk_{idx}"
            embedding = embed_text(chunk)
            if embedding:
                try:
                    doc_collection.add(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{"doc_id": doc_id_str, "user_id": user_id, "name": name, "chunk_index": idx}]
                    )
                    successful_embeddings += 1
                except Exception as e:
                    logging.error(f"Failed to add chunk {idx} to ChromaDB: {e}")
        
        logging.info(f"Successfully stored {successful_embeddings}/{len(chunks)} chunks in ChromaDB for doc_id {doc_id_str}")
        
        if successful_embeddings == 0:
            return jsonify({'detail': 'Failed to process document embeddings. Please try again.'}), 500
        
        return jsonify({
            "message": f"Document processed successfully: {name} ({successful_embeddings} chunks stored)",
            **doc
        }), 201
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
        doc_dict['uploaded_at'] = datetime.utcnow().isoformat() + 'Z'
        doc_dict['processed'] = True
        if doc_dict.get('url') is not None:
            doc_dict['url'] = str(doc_dict['url'])
            # Extract and process content from URL
            url_content = extract_text_from_url(doc_dict['url'])
            if not url_content or len(url_content.strip()) < 50:
                return jsonify({'detail': 'Could not extract meaningful content from the URL.'}), 400
            
            # Use improved document processing
            chunks = process_large_document(url_content)
            if not chunks:
                return jsonify({'detail': 'Could not process the URL content.'}), 400
            
            doc_dict['content'] = url_content  # Store original content
        else:
            return jsonify({'detail': 'URL is required for URL uploads.'}), 400
        
        result = db.documents.insert_one(doc_dict)
        doc_dict['_id'] = str(result.inserted_id)
        doc_id_str = doc_dict['_id']
        
        # Store embeddings for each chunk
        successful_embeddings = 0
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id_str}_chunk_{idx}"
            embedding = embed_text(chunk)
            if embedding:
                try:
                    doc_collection.add(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{"doc_id": doc_id_str, "user_id": user_id, "name": doc_dict['name'], "chunk_index": idx}]
                    )
                    successful_embeddings += 1
                except Exception as e:
                    logging.error(f"Failed to add chunk {idx} to ChromaDB: {e}")
        
        logging.info(f"Successfully stored {successful_embeddings}/{len(chunks)} chunks in ChromaDB for doc_id {doc_id_str}")
        
        if successful_embeddings == 0:
            return jsonify({'detail': 'Failed to process document embeddings. Please try again.'}), 500
        
        return jsonify({
            "message": f"URL processed successfully: {doc_dict['name']} ({successful_embeddings} chunks stored)",
            **doc_dict
        }), 201

@app.route('/documents', methods=['GET'])
def get_documents():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    docs = list(db.documents.find({'user_id': user_id}))
    for doc in docs:
        doc['_id'] = str(doc['_id'])
        # Add a flag instead of returning binary data
        doc['has_podcast'] = 'podcast_audio' in doc
        if 'podcast_audio' in doc:
            del doc['podcast_audio']  # Remove binary data from response
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

    # Support both audio and text input
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        file = request.files.get('audio')
        doc_id = request.form.get('doc_id')
        if not file or not doc_id:
            return jsonify({'detail': 'audio and doc_id are required.'}), 400
        try:
            pass
            # question = transcribe_audio(file)
        except Exception as e:
            return jsonify({'detail': f'Audio transcription failed: {str(e)}'}), 500
        # Instead of processing the chat, return the transcription for frontend editing
        return jsonify({'transcription': question}), 200
    else:
        data = request.json
        doc_id = data.get('doc_id')
        question = data.get('question')

    if not doc_id or not question:
        return jsonify({'detail': 'doc_id and question are required.'}), 400

    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    if not doc:
        return jsonify({'detail': 'Document not found or not authorized.'}), 404

    # Enhanced search strategy for better coverage
    selected_context = ""
    search_strategy = "semantic_search"
    
    try:
        # Get question embedding
        question_embedding = embed_text(question)
        if not question_embedding:
            return jsonify({'detail': 'Failed to process question. Please try again.'}), 500
        
        # Strategy 1: Semantic search with more results
        results = doc_collection.query(
            query_embeddings=[question_embedding],
            n_results=10,  # Increased from 5 to 10 for better coverage
            where={"doc_id": doc_id, "user_id": user_id}
        )
        
        if results and results['documents'] and len(results['documents'][0]) > 0:
            relevant_chunks = results['documents'][0]
            selected_context = "\n\n".join(relevant_chunks)
            logging.info(f"Found {len(relevant_chunks)} relevant chunks via semantic search")
            
            # If we found very few chunks, try additional strategies
            if len(relevant_chunks) < 3:
                search_strategy = "enhanced_search"
                # Strategy 2: Try with different question variations
                question_variations = [
                    question.lower(),
                    question.replace("?", "").replace("what", "").replace("how", "").replace("why", "").strip(),
                    " ".join([word for word in question.lower().split() if len(word) > 3])  # Keep only longer words
                ]
                
                additional_chunks = set()
                for variation in question_variations:
                    if len(variation.strip()) > 10:  # Only try meaningful variations
                        try:
                            var_embedding = embed_text(variation)
                            if var_embedding:
                                var_results = doc_collection.query(
                                    query_embeddings=[var_embedding],
                                    n_results=5,
                                    where={"doc_id": doc_id, "user_id": user_id}
                                )
                                if var_results and var_results['documents'] and len(var_results['documents'][0]) > 0:
                                    additional_chunks.update(var_results['documents'][0])
                        except Exception as e:
                            logging.error(f"Variation search failed: {e}")
                
                # Combine all found chunks
                all_chunks = list(set(relevant_chunks + list(additional_chunks)))
                if len(all_chunks) > len(relevant_chunks):
                    selected_context = "\n\n".join(all_chunks)
                    logging.info(f"Enhanced search found {len(all_chunks)} total chunks")
        else:
            search_strategy = "fallback_full_content"
            # Fallback to full document content if no embeddings found
            selected_context = doc.get('content', '')
            logging.info("No embeddings found, using full document content")
            
    except Exception as e:
        logging.error(f"Semantic search failed: {e}")
        search_strategy = "fallback_full_content"
        # Fallback to full document content
        selected_context = doc.get('content', '')
        logging.info("Using fallback to full document content")

    # If we still don't have enough context, try keyword-based approach
    if len(selected_context.strip()) < 1000 and search_strategy != "fallback_full_content":
        logging.info("Insufficient context found, trying keyword-based search")
        try:
            # Extract key terms from the question
            key_terms = [word.lower() for word in question.split() if len(word) > 3]
            
            # Get all chunks for this document
            all_chunks_results = doc_collection.get(
                where={"doc_id": doc_id, "user_id": user_id}
            )
            
            if all_chunks_results and all_chunks_results['documents']:
                keyword_matched_chunks = []
                for chunk in all_chunks_results['documents']:
                    chunk_lower = chunk.lower()
                    # Check if any key term appears in the chunk
                    if any(term in chunk_lower for term in key_terms):
                        keyword_matched_chunks.append(chunk)
                
                if keyword_matched_chunks:
                    selected_context = "\n\n".join(keyword_matched_chunks)
                    search_strategy = "keyword_search"
                    logging.info(f"Keyword search found {len(keyword_matched_chunks)} chunks")
                else:
                    # Last resort: use full content
                    selected_context = doc.get('content', '')
                    search_strategy = "fallback_full_content"
                    logging.info("No keyword matches, using full content")
        except Exception as e:
            logging.error(f"Keyword search failed: {e}")
            selected_context = doc.get('content', '')
            search_strategy = "fallback_full_content"

    # Truncate content if it's too large for the model
    selected_context = truncate_content_for_model(selected_context, max_tokens=80000)

    # Log the search strategy and context
    print("=== SEARCH STRATEGY ===")
    print(f"Strategy used: {search_strategy}")
    print(f"Context length: {len(selected_context)} characters")
    print(f"Estimated tokens: {estimate_tokens(selected_context)}")
    print("Context preview:", selected_context[:500] + "..." if len(selected_context) > 500 else selected_context)

    # Use the advanced, multi-step, context-aware, document-only Q&A prompt with greeting handling
    prompt = (
        "You are an advanced assistant designed to provide detailed and context-aware answers based solely on the content of the document provided. "
        "Always answer in the same language as the user's question. "
        "If the answer is not present in the document, reply: 'The answer is not present in the document.' Do not repeat this message unnecessarily. "
        "The user will ask a question in their own words. You must perform the following steps:\n\n"
        "1. **Interpretation**: Analyze the user's question and identify the specific information being requested.\n   "
        "2. **Content Search**: Carefully search the document for all relevant information. If the document contains multiple sections that are related to the user's query, consider how they relate to each other and use them to build a comprehensive answer.\n   "
        "3. **Answer Structuring**: Format your answer clearly and concisely. \n   - If the information is available in the document, summarize and present it in an organized way, making sure your answer directly addresses the user's question.\n   - If the question requires multiple steps or a multi-faceted answer, break down the response logically, ensuring clarity in each part of the answer.\n   "
        "4. **Contextual Awareness**: Use the surrounding context in the document to interpret the meaning of terms and concepts. If a specific term, acronym, or phrase is unclear in the question, use context from the document to define or explain it.\n   "
        "5. **Fallback for Missing Information**: If the document does not contain sufficient information to provide a definitive answer, respond with the following message: \n   - **'The answer is not present in the document.'**\n   - Avoid speculation or external references, and ensure that the response does not veer off-topic.\n   "
        "6. **Edge Cases Handling**: \n   - If the question is ambiguous or could be interpreted in multiple ways, provide a clarifying message asking the user to rephrase or specify further details.\n   - If the user asks for an opinion or subjective information that cannot be derived from the document, politely explain that the document only contains factual information, and you cannot provide subjective insights.\n   "
        "7. **Greetings Handling**: If the user's question is a greeting (such as 'hi', 'hello', etc.), respond in a friendly, conversational manner as a human would, regardless of the document content.\n\n"
        "8. **Term Variations**: If the user's question uses a term that is a minor variation (such as different capitalization, hyphenation, or spacing) of a term in the document, treat them as referring to the same concept and answer accordingly.\n\n"
        "**Document Content:**\n" + selected_context + "\n\n**User's Question:**\n" + question + "\n\n**Your Answer:**\n"
    )
    
    # Check if the total prompt would exceed token limits
    total_estimated_tokens = estimate_tokens(prompt)
    if total_estimated_tokens > 120000:  # Leave some buffer
        # Further truncate the context
        selected_context = truncate_content_for_model(selected_context, max_tokens=60000)
        prompt = (
            "You are an advanced assistant designed to provide detailed and context-aware answers based solely on the content of the document provided. "
            "Always answer in the same language as the user's question. "
            "If the answer is not present in the document, reply: 'The answer is not present in the document.' Do not repeat this message unnecessarily. "
            "**Document Content:**\n" + selected_context + "\n\n**User's Question:**\n" + question + "\n\n**Your Answer:**\n"
        )
        logging.info(f"Prompt truncated to approximately {estimate_tokens(prompt)} tokens")
    
    print("=== PROMPT SENT TO MODEL ===")
    print(f"Total estimated tokens: {estimate_tokens(prompt)}")
    answer = scan_with_gpt(prompt)
    print("=== MODEL RESPONSE ===")
    print(answer)

    # Store chat history
    chat_msg = ChatMessage(
        user_id=user_id,
        doc_id=doc_id,
        question=question,
        answer=answer,
        timestamp=datetime.utcnow().isoformat() + 'Z'
    )
    db.chats.insert_one(chat_msg.dict())
    return jsonify({"answer": answer})
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

@app.route('/api/convert_to_podcast', methods=['POST'])
def convert_to_podcast():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401

    data = request.json
    doc_id = data.get('doc_id')
    if not doc_id:
        return jsonify({'detail': 'Document ID is required.'}), 400

    # Retrieve document from DB
    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    if not doc:
        return jsonify({'detail': 'Document not found.'}), 404

    content = doc.get('content', '')
    if not content or len(content.strip()) < 50:
        return jsonify({'detail': 'Document content is empty or too short.'}), 400

    # Summarize/truncate to ~10 minutes (about 1400 words)
    max_words_for_summary = 20000
    words = content.split()
    if len(words) > 1400:
        # Only summarize the first 20,000 words to avoid context length errors
        if len(words) > max_words_for_summary:
            content_to_summarize = ' '.join(words[:max_words_for_summary])
        else:
            content_to_summarize = content
        user = db.users.find_one({'_id': ObjectId(user_id)})
        user_name = user.get('username', 'User') if user else 'User'
        expert_name = 'Expert'
        summary_prompt = f"""
            Please convert the following document into a 10-minute conversational podcast script between two speakers, {user_name} and {expert_name}. Use ONLY the names {user_name} and {expert_name} as speakers in the script. Do NOT use Alice or Bob. {user_name} should ask insightful questions about the document, and {expert_name} should answer them in detail, explaining the key points, facts, and concepts. Make the conversation natural, engaging, and informative, as if {user_name} is curious and {expert_name} is knowledgeable. Limit the script to about 1400 words.\n\nDocument content:\n{content_to_summarize}
        
        Document content:
        {content_to_summarize}
        """
        try:
            summary = scan_with_gpt(summary_prompt)
        except Exception as e:
            return jsonify({'detail': f'Summarization failed: {str(e)}'}), 500
        podcast_text = summary
    else:
        podcast_text = content

    # Prepend the document title to the podcast script
    doc_title = doc.get('name', 'Untitled Document')
    podcast_text = f"This podcast is based on the selected document : {doc_title}.\n\n" + podcast_text

    # Truncate to 1400 words if still too long
    podcast_words = podcast_text.split()[:1400]
    podcast_text = ' '.join(podcast_words)

    # Convert to audio using gTTS (Alice) and Coqui TTS (Bob) for two voices
    try:
        tts = gTTS(text=podcast_text, lang='en')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_bytes = audio_fp.getvalue()
        db.documents.update_one({'_id': ObjectId(doc_id), 'user_id': user_id}, {'$set': {'podcast_audio': audio_bytes}})
        audio_fp.seek(0)
    except Exception as e:
        import traceback
        print('--- PODCAST SCRIPT ---')
        print(podcast_text)
        print('--- TTS ERROR ---')
        print(traceback.format_exc())
        return jsonify({'detail': f'TTS failed: {str(e)}', 'trace': traceback.format_exc()}), 500

    return send_file(
        audio_fp,
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name=f"podcast_{doc_id}.mp3"
    )

@app.route('/api/podcast/<doc_id>', methods=['GET'])
def get_podcast_audio(doc_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    if not doc or 'podcast_audio' not in doc:
        return jsonify({'detail': 'Podcast audio not found.'}), 404
    audio_bytes = doc['podcast_audio']
    return send_file(
        io.BytesIO(audio_bytes),
        mimetype='audio/mpeg',
        as_attachment=False,
        download_name=f"podcast_{doc_id}.mp3"
    )

@app.route('/api/podcast/<doc_id>', methods=['DELETE'])
def delete_podcast_audio(doc_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    result = db.documents.update_one({'_id': ObjectId(doc_id), 'user_id': user_id}, {'$unset': {'podcast_audio': ''}})
    if result.modified_count == 1:
        return jsonify({'message': 'Podcast audio deleted successfully.'}), 200
    else:
        return jsonify({'detail': 'Podcast audio not found or not authorized.'}), 404

@app.route('/api/podcast_script/<doc_id>', methods=['GET'])
def get_podcast_script(doc_id):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'detail': 'Authentication required.'}), 401
    doc = db.documents.find_one({'_id': ObjectId(doc_id), 'user_id': user_id})
    if not doc:
        return jsonify({'detail': 'Document not found.'}), 404
    # Regenerate the script using the same logic as convert_to_podcast
    content = doc.get('content', '')
    if not content or len(content.strip()) < 50:
        return jsonify({'detail': 'Document content is empty or too short.'}), 400
    max_words_for_summary = 20000
    words = content.split()
    if len(words) > 1400:
        # Define user_name and expert_name before using them in the prompt
        user = db.users.find_one({'_id': ObjectId(user_id)})
        user_name = user.get('username', 'User') if user else 'User'
        expert_name = 'Expert'
        if len(words) > max_words_for_summary:
            content_to_summarize = ' '.join(words[:max_words_for_summary])
        else:
            content_to_summarize = content
        summary_prompt = f"""
        Please convert the following document into a 10-minute conversational podcast script between two speakers, {user_name} and {expert_name}. Use ONLY the names {user_name} and {expert_name} as speakers in the script. Do NOT use Alice or Bob. {user_name} should ask insightful questions about the document, and {expert_name} should answer them in detail, explaining the key points, facts, and concepts. Make the conversation natural, engaging, and informative, as if {user_name} is curious and {expert_name} is knowledgeable. Limit the script to about 1400 words.\n\nDocument content:\n{content_to_summarize}
        """
        try:
            script = scan_with_gpt(summary_prompt)
        except Exception as e:
            return jsonify({'detail': f'Script generation failed: {str(e)}'}), 500
    else:
        script = content
    # Return as downloadable text file
    from flask import Response
    return Response(
        script,
        mimetype='text/plain',
        headers={"Content-Disposition": f"attachment;filename=podcast_script_{doc_id}.txt"}
    )

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return jsonify({"detail": str(e), "trace": traceback.format_exc()}), 500

if __name__ == "__main__":
    app.run(debug=True) 