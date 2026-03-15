from flask import Flask, Response, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import hashlib
import json
import logging
import os
import re
import time
import uuid
import fitz  # PyMuPDF
from langchain_groq import ChatGroq
import pymysql
from contextlib import contextmanager
import pandas as pd
import joblib
import random
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables from .env located next to this file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize LLM (optional, based on environment)
_groq_key = os.environ.get("GROQ_API_KEY")
llm = (
    ChatGroq(
        temperature=0,
        groq_api_key=_groq_key or "not-set",
        model_name="llama-3.3-70b-versatile",
    )
    if _groq_key
    else None
)

# Initialize ML Model for grade prediction
try:
    ml_model = joblib.load('grade_predictor_model.joblib')
    with open('grade_mapping.json', 'r') as f:
        grade_mapping_reverse = json.load(f)
    logger.info("ML grade prediction model loaded successfully")
except Exception as e:
    logger.warning("Could not load ML model: %s", e)
    ml_model = None
    grade_mapping_reverse = None

def predict_grade(cia1, cia2, cia3):
    """Predict final grade based on CIA scores."""
    if ml_model is None or grade_mapping_reverse is None:
        return None
    try:
        prediction = ml_model.predict([[cia1, cia2, cia3]])[0]
        # Try both int and float formats for the mapping
        pred_key = str(int(prediction))
        if pred_key not in grade_mapping_reverse:
            pred_key = str(float(prediction))
        grade = grade_mapping_reverse.get(pred_key, 'Unknown')
        return grade
    except Exception as e:
        logger.error("Prediction error: %s", e)
        return None

def safe_id(value):
    """Strip non-alphanumeric chars to prevent path traversal in filenames."""
    return re.sub(r'[^a-zA-Z0-9_-]', '', str(value))

############################################################
# MySQL (PyMySQL) auth storage for professors only
############################################################

def get_db_conn():
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', 'mysql'),
        database=os.getenv('MYSQL_DB', 'university'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

@contextmanager
def db_cursor():
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()

def get_professor_by_id(prof_id):
    try:
        with db_cursor() as cur:
            cur.execute("SELECT id, name, password_hash FROM professors WHERE id=%s", (prof_id,))
            return cur.fetchone()
    except Exception as e:
        logger.error("DB error (get_professor_by_id): %s", e)
        return None

def create_professor(prof_id, name, password):
    try:
        password_hash = generate_password_hash(password)
        with db_cursor() as cur:
            cur.execute(
                "INSERT INTO professors (id, name, password_hash) VALUES (%s, %s, %s)",
                (prof_id, name, password_hash)
            )
        return True
    except Exception as e:
        logger.error("DB error (create_professor): %s", e)
        return False

def get_professor_classes(prof_id):
    """Get all classes for a professor."""
    conn = get_db_conn()
    try:
        # Use regular cursor to get tuples (not DictCursor)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM classes WHERE professor_id = %s ORDER BY name",
                (prof_id,)
            )
            result = cur.fetchall()
            logger.debug("get_professor_classes: Found %d classes for %s", len(result), prof_id)
            # Result should be a tuple of tuples
            return result
    except Exception as e:
        logger.error("DB error (get_professor_classes): %s", e, exc_info=True)
        return []
    finally:
        conn.close()

def get_class_by_id(class_id):
    """Get a class by ID."""
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, name, professor_id FROM classes WHERE id = %s",
                (class_id,)
            )
            return cur.fetchone()
    except Exception as e:
        logger.error("DB error (get_class_by_id): %s", e)
        return None

def create_class(prof_id, class_name):
    """Create a new class for a professor."""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            unique_str = f"{prof_id}_{class_name}_{time.time()}"
            class_id = hashlib.md5(unique_str.encode()).hexdigest()[:16]

            logger.info("Creating class: id=%s, prof_id=%s, name=%s", class_id, prof_id, class_name)
            cur.execute(
                "INSERT INTO classes (id, professor_id, name) VALUES (%s, %s, %s)",
                (class_id, prof_id, class_name)
            )
        conn.commit()
        logger.info("Class created successfully: %s", class_id)
        return class_id
    except Exception as e:
        logger.error("DB error (create_class): %s", e, exc_info=True)
        conn.rollback()
        return None
    finally:
        conn.close()

# Simple file-based storage for boards
def load_board_data(prof_id, class_id=None):
    if class_id:
        filename = f"board_{safe_id(prof_id)}_class{safe_id(class_id)}.json"
    else:
        filename = f"board_{safe_id(prof_id)}.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {
        'tasks': {
            't1': {'id': 't1', 'title': 'Welcome to your Kanban Board', 'desc': 'This is your personal task management board', 'status': 'backlog', 'prio': 'med', 'due': None, 'label': 'welcome', 'order': 1000},
            't2': {'id': 't2', 'title': 'Create your first task', 'desc': 'Click the + New Task button to get started', 'status': 'backlog', 'prio': 'low', 'due': None, 'label': 'tutorial', 'order': 2000}
        }
    }

def save_board_data(prof_id, data, class_id=None):
    if class_id:
        filename = f"board_{safe_id(prof_id)}_class{safe_id(class_id)}.json"
    else:
        filename = f"board_{safe_id(prof_id)}.json"
    with open(filename, 'w') as f:
        json.dump(data, f)

# Syllabus processing functions
def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.error("Error reading PDF: %s", e)
        return None
    return text

def process_syllabus_with_llm(pdf_text):
    """Process syllabus text with LLM to extract tasks."""
    if llm is None:
        logger.warning("Syllabus LLM is not configured. Set GROQ_API_KEY in the environment.")
        return None
    prompt = f"""
    You are a syllabus parser. Extract all assignments, deadlines, and tasks from this syllabus and return ONLY valid JSON in this exact format:

    {{
      "tasks": {{
        "task_id": {{
          "id": "task_id",
          "title": "Task Title",
          "desc": "Task Description",
          "status": "backlog",
          "prio": "high|med|low",
          "due": null,
          "label": "assignment|exam|reading|project",
          "order": 1000
        }}
      }}
    }}

    Rules:
    - Use "backlog" as default status for all tasks
    - Set priority: "high" for exams/final projects, "med" for major assignments, "low" for readings/homework
    - Always set "due" to null — professors will add dates manually
    - Use descriptive labels: "exam", "assignment", "reading", "project", "presentation"
    - Generate unique task IDs like "syl_001", "syl_002", etc.
    - Set order values incrementally (1000, 2000, 3000...)
    - Include all deadlines, readings, assignments, and exams
    - Make titles clear and actionable

    IMPORTANT: Return ONLY the JSON object, no additional text or explanations.

    Here is the syllabus text:
    {pdf_text}
    """

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        logger.error("LLM processing error: %s", e)
        return None

# Routes
# Serve static files (for localtunnel support)
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/app.js')
def serve_js():
    return send_from_directory('.', 'app.js', mimetype='application/javascript')

@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css', mimetype='text/css')

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    prof_id = data.get('prof_id')
    password = data.get('password')
    
    if not prof_id or not password:
        return jsonify({'error': 'Professor ID and password required'}), 400
    
    professor = get_professor_by_id(prof_id)
    
    if professor and check_password_hash(professor['password_hash'], password):
        session['professor_id'] = professor['id']
        return jsonify({
            'success': True,
            'professor': {
                'id': professor['id'],
                'prof_id': professor['id'],
                'name': professor['name']
            }
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    prof_id = data.get('prof_id')
    name = data.get('name')
    password = data.get('password')
    
    if not prof_id or not name or not password:
        return jsonify({'error': 'Professor ID, name, and password required'}), 400
    
    # Check if professor already exists (MySQL)
    if get_professor_by_id(prof_id):
        return jsonify({'error': 'Professor ID already exists'}), 400
    
    # Create new professor (MySQL)
    ok = create_professor(prof_id, name, password)
    if not ok:
        return jsonify({'error': 'Failed to create professor'}), 500
    
    # Create welcome board for new professor
    welcome_board = {
        'tasks': {
            't1': {
                'id': 't1', 
                'title': 'Welcome to your Kanban Board', 
                'desc': 'This is your personal task management board', 
                'status': 'backlog', 
                'prio': 'med', 
                'due': None, 
                'label': 'welcome',
                'order': 1000
            },
            't2': {
                'id': 't2', 
                'title': 'Create your first task', 
                'desc': 'Click the + New Task button to get started', 
                'status': 'backlog', 
                'prio': 'low', 
                'due': None, 
                'label': 'tutorial',
                'order': 2000
            }
        }
    }
    save_board_data(prof_id, welcome_board)
    
    return jsonify({
        'success': True,
        'message': 'Account created successfully',
        'professor': {
            'id': prof_id,
            'prof_id': prof_id,
            'name': name
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'professor_id' in session:
        professor = get_professor_by_id(session['professor_id'])
        if not professor:
            return jsonify({'authenticated': False})
        return jsonify({
            'authenticated': True,
            'professor': {
                'id': professor['id'],
                'prof_id': professor['id'],
                'name': professor['name']
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Get all classes for the logged-in professor."""
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        prof_id = session['professor_id']
        logger.debug("Getting classes for professor %s", prof_id)
        classes_tuples = get_professor_classes(prof_id)
        logger.debug("Raw classes from DB (type: %s): %s", type(classes_tuples), classes_tuples)
        
        # Convert to dictionaries if needed
        # Check if data is already in dict format or tuple format
        classes = []
        if classes_tuples:
            for cls in classes_tuples:
                try:
                    if isinstance(cls, dict):
                        # Already a dictionary, use it directly
                        classes.append({'id': str(cls['id']), 'name': str(cls['name'])})
                    elif isinstance(cls, (tuple, list)):
                        # Tuple format: (id, name)
                        class_id = str(cls[0])
                        class_name = str(cls[1])
                        classes.append({'id': class_id, 'name': class_name})
                    else:
                        logger.warning("Unexpected class format: %s - %s", type(cls), cls)
                except (IndexError, TypeError, KeyError) as e:
                    logger.error("Error processing class %s: %s", cls, e)
                    continue
        
        logger.debug("Converted %d classes: %s", len(classes), classes)
        return jsonify({'success': True, 'classes': classes})
    except Exception as e:
        logger.error("Error in get_classes: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to get classes'}), 500

@app.route('/api/classes', methods=['POST'])
def create_new_class():
    """Create a new class for the logged-in professor."""
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        prof_id = session['professor_id']
        data = request.get_json()
        logger.debug("Create class request: prof_id=%s, data=%s", prof_id, data)
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        class_name = data.get('name')
        
        if not class_name:
            return jsonify({'error': 'Class name required'}), 400
        
        class_id = create_class(prof_id, class_name)
        if not class_id:
            return jsonify({'error': 'Failed to create class. Check server logs.'}), 500
        
        return jsonify({
            'success': True,
            'message': 'Class created successfully',
            'class': {'id': class_id, 'name': class_name}
        })
    except Exception as e:
        logger.error("Error in create_new_class: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to create class'}), 500

@app.route('/api/board', methods=['GET'])
def get_board():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    prof_id = session['professor_id']
    class_id = request.args.get('class_id')
    board_data = load_board_data(prof_id, class_id)
    return jsonify(board_data)

@app.route('/api/board/tasks', methods=['POST'])
def create_task():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    prof_id = session['professor_id']
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    class_id = request.args.get('class_id') or data.get('class_id')
    board_data = load_board_data(prof_id, class_id)
    task_id = 't' + str(uuid.uuid4())[:7]

    task = {
        'id': task_id,
        'title': data.get('title', ''),
        'desc': data.get('desc', ''),
        'status': data.get('status', 'backlog'),
        'prio': data.get('prio', 'med'),
        'due': data.get('due'),
        'label': data.get('label', ''),
        'order': data.get('order', 0)
    }
    
    board_data['tasks'][task_id] = task
    save_board_data(prof_id, board_data, class_id)
    
    return jsonify({
        'success': True,
        'task': task
    })

@app.route('/api/board/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    prof_id = session['professor_id']
    data = request.get_json() or {}
    class_id = request.args.get('class_id') or data.get('class_id')
    board_data = load_board_data(prof_id, class_id)
    
    if task_id not in board_data['tasks']:
        return jsonify({'error': 'Task not found'}), 404
    
    board_data['tasks'][task_id].update({
        'title': data.get('title', board_data['tasks'][task_id]['title']),
        'desc': data.get('desc', board_data['tasks'][task_id]['desc']),
        'status': data.get('status', board_data['tasks'][task_id]['status']),
        'prio': data.get('prio', board_data['tasks'][task_id]['prio']),
        'due': data.get('due', board_data['tasks'][task_id]['due']),
        'label': data.get('label', board_data['tasks'][task_id]['label']),
        'order': data.get('order', board_data['tasks'][task_id]['order'])
    })
    
    save_board_data(prof_id, board_data, class_id)
    return jsonify({'success': True})

@app.route('/api/board/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    prof_id = session['professor_id']
    class_id = request.args.get('class_id')
    board_data = load_board_data(prof_id, class_id)
    
    if task_id not in board_data['tasks']:
        return jsonify({'error': 'Task not found'}), 404
    
    del board_data['tasks'][task_id]
    save_board_data(prof_id, board_data, class_id)
    return jsonify({'success': True})

@app.route('/api/board/export', methods=['GET'])
def export_board():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    prof_id = session['professor_id']
    class_id = request.args.get('class_id')
    board_data = load_board_data(prof_id, class_id)
    try:
        payload = json.dumps(board_data, ensure_ascii=False, separators=(',', ':'))
        filename = f"board_{prof_id}" + (f"_class{class_id}" if class_id else "") + ".json"
        resp = Response(payload, mimetype='application/json; charset=utf-8')
        resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        logger.error("Export error: %s", e)
        return jsonify({'error': 'Failed to export board'}), 500

@app.route('/api/board/import', methods=['POST'])
def import_board():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    prof_id = session['professor_id']
    class_id = request.form.get('class_id') or request.args.get('class_id')
    mode = (request.args.get('mode') or 'merge').lower()  # merge|replace

    # Accept either JSON body or a file upload with key 'file'
    incoming_json = None
    try:
        if 'file' in request.files:
            f = request.files['file']
            text = f.read().decode('utf-8')
            incoming_json = json.loads(text)
        else:
            incoming_json = request.get_json(force=True, silent=False)
    except Exception as e:
        logger.error("Import parse error: %s", e)
        return jsonify({'error': 'Invalid JSON provided'}), 400

    if not isinstance(incoming_json, dict) or 'tasks' not in incoming_json or not isinstance(incoming_json['tasks'], dict):
        return jsonify({'error': 'Invalid board format: missing tasks object'}), 400

    current_board = load_board_data(prof_id, class_id)
    if mode == 'replace':
        new_board = {'tasks': incoming_json['tasks']}
    else:
        new_board = {'tasks': {**current_board.get('tasks', {}), **incoming_json['tasks']}}

    save_board_data(prof_id, new_board, class_id)
    return jsonify({'success': True, 'imported': len(incoming_json['tasks']), 'mode': mode})

@app.route('/api/board/tasks/move', methods=['POST'])
def move_task():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    prof_id = session['professor_id']
    data = request.get_json()
    class_id = request.args.get('class_id') or (data.get('class_id') if data else None)
    board_data = load_board_data(prof_id, class_id)
    
    task_id = data.get('task_id')
    new_status = data.get('status')
    new_order = data.get('order', 0)
    
    if task_id not in board_data['tasks']:
        return jsonify({'error': 'Task not found'}), 404
    
    board_data['tasks'][task_id]['status'] = new_status
    board_data['tasks'][task_id]['order'] = new_order
    save_board_data(prof_id, board_data, class_id)
    
    return jsonify({'success': True})

@app.route('/api/syllabus/upload', methods=['POST'])
def upload_syllabus():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    # Ensure LLM is configured before accepting uploads
    if llm is None:
        return (
            jsonify(
                {
                    "error": "Syllabus AI not configured. Set GROQ_API_KEY in environment."
                }
            ),
            503,
        )
    
    if 'syllabus' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['syllabus']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(filepath)
        if not pdf_text:
            return jsonify({'error': 'Could not extract text from PDF'}), 400
        
        # Process with LLM
        llm_response = process_syllabus_with_llm(pdf_text)
        if not llm_response:
            return jsonify({'error': 'Failed to process syllabus with AI'}), 500
        
        # Parse LLM response as JSON
        try:
            # Try to extract JSON from the response (AI might add extra text)
            llm_text = llm_response.strip()
            
            # Look for JSON object in the response
            if '{' in llm_text and '}' in llm_text:
                # Find the first { and last } to extract JSON
                start = llm_text.find('{')
                end = llm_text.rfind('}') + 1
                json_text = llm_text[start:end]
                syllabus_data = json.loads(json_text)
            else:
                raise json.JSONDecodeError("No JSON found in response", llm_text, 0)
                
        except json.JSONDecodeError as e:
            logger.error("JSON parsing error: %s", e)
            logger.debug("LLM response: %s...", llm_response[:500])
            return jsonify({'error': 'AI returned invalid JSON format'}), 500
        
        # Get current board data
        prof_id = session['professor_id']
        class_id = request.form.get('class_id') or request.args.get('class_id')
        current_board = load_board_data(prof_id, class_id)
        
        # Remove placeholder welcome cards and merge new tasks
        if 'tasks' in syllabus_data:
            current_board['tasks'].pop('t1', None)
            current_board['tasks'].pop('t2', None)
            current_board['tasks'].update(syllabus_data['tasks'])
            save_board_data(prof_id, current_board, class_id)
        
        # Clean up uploaded file
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'message': f'Successfully processed syllabus and added {len(syllabus_data.get("tasks", {}))} tasks',
            'tasks': syllabus_data.get('tasks', {})
        })
        
    except Exception as e:
        logger.error("Syllabus processing error: %s", e)
        return jsonify({'error': 'Failed to process syllabus'}), 500

def load_student_selections(prof_id, class_id):
    """Load selected roll numbers for a class, or sample 60 if not exists"""
    if class_id:
        filename = f"students_{safe_id(prof_id)}_class{safe_id(class_id)}.json"
    else:
        filename = f"students_{safe_id(prof_id)}.json"

    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return data.get('roll_numbers', [])
    return None  # Need to initialize

def save_student_selections(prof_id, class_id, roll_numbers):
    """Save selected roll numbers for a class"""
    if class_id:
        filename = f"students_{safe_id(prof_id)}_class{safe_id(class_id)}.json"
    else:
        filename = f"students_{safe_id(prof_id)}.json"
    
    with open(filename, 'w') as f:
        json.dump({'roll_numbers': roll_numbers}, f)

@app.route('/api/students/analytics', methods=['GET'])
def get_student_analytics():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        prof_id = session['professor_id']
        class_id = request.args.get('class_id')
        
        csv_path = 'student_dataset.csv'
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Student dataset not found'}), 404
        
        # Read student dataset
        df = pd.read_csv(csv_path)
        logger.debug("CSV loaded. Shape: %s, Columns: %s", df.shape, df.columns.tolist())
        
        # Check if required columns exist
        required_cols = ['Roll No.', 'Student_Names', 'CIA_1', 'CIA_2', 'CIA_3', 'Grade']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return jsonify({'error': f'Missing required columns: {missing_cols}'}), 400
        
        df = df[required_cols].dropna()
        logger.debug("After dropna. Shape: %s", df.shape)
        
        if df.empty:
            return jsonify({'error': 'No valid student data found in dataset'}), 404
        
        # Get selected students for this class
        selected_roll_nos = load_student_selections(prof_id, class_id)
        
        # Ensure Roll No. is int type for consistent comparison
        df['Roll No.'] = pd.to_numeric(df['Roll No.'], errors='coerce')
        df = df.dropna(subset=['Roll No.'])  # Remove rows with invalid roll numbers
        df['Roll No.'] = df['Roll No.'].astype(int)
        
        # If no selections exist, sample 60 and save them
        if selected_roll_nos is None:
            if len(df) > 60:
                sampled_df = df.sample(n=60, random_state=42)
                selected_roll_nos = sampled_df['Roll No.'].tolist()
            else:
                selected_roll_nos = df['Roll No.'].tolist()
            save_student_selections(prof_id, class_id, selected_roll_nos)
        
        # Filter to only selected students (ensure type consistency)
        df = df[df['Roll No.'].isin(selected_roll_nos)]
        logger.debug("After filtering. Shape: %s, Selected roll nos: %d", df.shape, len(selected_roll_nos))
        
        if df.empty:
            return jsonify({'error': 'No students found for this class'}), 404
        
        students = []
        for _, row in df.iterrows():
            try:
                roll_no = row['Roll No.']
                cia1 = float(row['CIA_1'])
                cia2 = float(row['CIA_2'])
                cia3 = float(row['CIA_3'])

                predicted_grade = predict_grade(cia1, cia2, cia3)
                actual_grade = str(row['Grade'])

                students.append({
                    'roll_no': str(int(roll_no)),
                    'name': str(row['Student_Names']),
                    'cia1': cia1,
                    'cia2': cia2,
                    'cia3': cia3,
                    'grade': predicted_grade if predicted_grade else actual_grade,
                    'actual_grade': actual_grade,
                    'is_predicted': predicted_grade is not None
                })
            except Exception as e:
                logger.error("Error processing student row: %s", e)
                continue
        
        students.sort(key=lambda x: int(x['roll_no']) if x['roll_no'].isdigit() else 999999)
        
        return jsonify({
            'success': True,
            'students': students,
            'total': len(students)
        })
        
    except Exception as e:
        logger.error("Analytics error: %s", e, exc_info=True)
        return jsonify({'error': 'Failed to load student analytics'}), 500

@app.route('/api/students/<roll_no>', methods=['GET'])
def get_student_details(roll_no):
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        csv_path = 'student_dataset.csv'
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Student dataset not found'}), 404
        
        df = pd.read_csv(csv_path)
        
        # Find student
        mask = df['Roll No.'].astype(str) == str(roll_no)
        if not mask.any():
            return jsonify({'error': 'Student not found'}), 404
        
        student_row = df[mask].iloc[0]
        
        return jsonify({
            'success': True,
            'student': {
                'roll_no': str(student_row['Roll No.']),
                'name': str(student_row['Student_Names']),
                'cia1': float(student_row['CIA_1']),
                'cia2': float(student_row['CIA_2']),
                'cia3': float(student_row['CIA_3']),
                'grade': str(student_row['Grade']),
                'phone': str(student_row.get('Phone_No.', '')),
                'comment': str(student_row['Comment'])
            }
        })
        
    except Exception as e:
        logger.error("Get student error: %s", e)
        return jsonify({'error': 'Failed to get student details'}), 500

@app.route('/api/students', methods=['POST'])
def create_student():
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        prof_id = session['professor_id']
        class_id = request.args.get('class_id')
        data = request.get_json()
        csv_path = 'student_dataset.csv'
        
        # Read existing data
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
        else:
            # Create new dataframe with column headers
            df = pd.DataFrame(columns=['Student_Names', 'Phone_No.', 'CIA_1', 'CIA_2', 'CIA_3', 'Grade', 'Comment', 'Roll No.', 'School Name', 'Student Address'])
        
        # Generate new roll number if not provided
        roll_no = data.get('roll_no')
        if not roll_no:
            if not df.empty and 'Roll No.' in df.columns:
                # Ensure Roll No. is numeric for max calculation
                df_temp = df.copy()
                df_temp['Roll No.'] = pd.to_numeric(df_temp['Roll No.'], errors='coerce')
                max_roll = df_temp['Roll No.'].max()
                roll_no = str(int(max_roll) + 1) if pd.notna(max_roll) else '1'
            else:
                roll_no = '1'
        
        # Ensure roll_no is stored as int in CSV for consistency
        roll_no_int = int(roll_no)
        
        # Get CIA scores
        cia1 = float(data.get('cia1', 0))
        cia2 = float(data.get('cia2', 0))
        cia3 = float(data.get('cia3', 0))

        # Predict grade using ML model if available
        predicted_grade = predict_grade(cia1, cia2, cia3) or 'F'

        # Create new student row
        new_student = pd.DataFrame({
            'Student_Names': [data.get('name', 'Unknown')],
            'Phone_No.': [data.get('phone', 'N/A')],
            'CIA_1': [cia1],
            'CIA_2': [cia2],
            'CIA_3': [cia3],
            'Grade': [predicted_grade],
            'Comment': [data.get('comment', '')],
            'Roll No.': [roll_no_int],  # Store as int for consistency
            'School Name': [data.get('school', 'N/A')],
            'Student Address': [data.get('address', 'N/A')]
        })
        
        # Append to dataframe
        df = pd.concat([df, new_student], ignore_index=True)
        
        # Save to CSV
        df.to_csv(csv_path, index=False)
        
        # Add to class selection if class_id provided
        if class_id:
            selected_roll_nos = load_student_selections(prof_id, class_id)
            logger.debug("Adding student %d to class %s. Current selections: %s", roll_no_int, class_id, selected_roll_nos)
            if selected_roll_nos is None:
                # Initialize with this student
                selected_roll_nos = [roll_no_int]
            elif roll_no_int not in selected_roll_nos:
                selected_roll_nos.append(roll_no_int)
            logger.debug("Saving selections: %s", selected_roll_nos)
            save_student_selections(prof_id, class_id, selected_roll_nos)
        else:
            logger.warning("No class_id provided when adding student %d", roll_no_int)
        
        return jsonify({'success': True, 'message': 'Student added successfully', 'roll_no': roll_no})
        
    except Exception as e:
        logger.error("Create student error: %s", e)
        return jsonify({'error': 'Failed to create student'}), 500

@app.route('/api/students/<roll_no>', methods=['PUT'])
def update_student(roll_no):
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json()
        csv_path = 'student_dataset.csv'
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Student dataset not found'}), 404
        
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Find and update student
        mask = df['Roll No.'].astype(str) == str(roll_no)
        if not mask.any():
            return jsonify({'error': 'Student not found'}), 404
        
        # Check if any CIA scores changed - need to repredict grade
        marks_changed = 'cia1' in data or 'cia2' in data or 'cia3' in data

        # Update fields if provided
        if 'name' in data:
            df.loc[mask, 'Student_Names'] = data['name']
        if 'phone' in data:
            df.loc[mask, 'Phone_No.'] = data['phone']
        if 'cia1' in data:
            df.loc[mask, 'CIA_1'] = float(data['cia1'])
        if 'cia2' in data:
            df.loc[mask, 'CIA_2'] = float(data['cia2'])
        if 'cia3' in data:
            df.loc[mask, 'CIA_3'] = float(data['cia3'])

        # Auto-predict grade if scores changed, unless grade is explicitly provided
        if marks_changed and 'grade' not in data:
            cia1 = float(df.loc[mask, 'CIA_1'].iloc[0] if 'cia1' not in data else data['cia1'])
            cia2 = float(df.loc[mask, 'CIA_2'].iloc[0] if 'cia2' not in data else data['cia2'])
            cia3 = float(df.loc[mask, 'CIA_3'].iloc[0] if 'cia3' not in data else data['cia3'])
            predicted_grade = predict_grade(cia1, cia2, cia3)
            if predicted_grade:
                df.loc[mask, 'Grade'] = predicted_grade
        elif 'grade' in data:
            df.loc[mask, 'Grade'] = data['grade']
        
        if 'comment' in data:
            df.loc[mask, 'Comment'] = data['comment']
        if 'school' in data:
            df.loc[mask, 'School Name'] = data['school']
        if 'address' in data:
            df.loc[mask, 'Student Address'] = data['address']
        
        # Save updated CSV
        df.to_csv(csv_path, index=False)
        
        return jsonify({'success': True, 'message': 'Student updated successfully'})
        
    except Exception as e:
        logger.error("Update student error: %s", e)
        return jsonify({'error': 'Failed to update student'}), 500

@app.route('/api/students/<roll_no>', methods=['DELETE'])
def delete_student(roll_no):
    if 'professor_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        csv_path = 'student_dataset.csv'
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Student dataset not found'}), 404
        
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Find and delete student
        mask = df['Roll No.'].astype(str) == str(roll_no)
        if not mask.any():
            return jsonify({'error': 'Student not found'}), 404
        
        df = df[~mask]
        
        # Save updated CSV
        df.to_csv(csv_path, index=False)
        
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
        
    except Exception as e:
        logger.error("Delete student error: %s", e)
        return jsonify({'error': 'Failed to delete student'}), 500

# CORS support
@app.after_request
def after_request(response):
    # When using credentials: 'include', we can't use wildcard for Access-Control-Allow-Origin.
    # Dynamically allow only known dev origins.
    origin = request.headers.get("Origin")
    allowed_origins = {
        "http://localhost:5001",
        "http://127.0.0.1:5001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Professor Kanban Backend...")
    logger.info("Auth: using MySQL for professor accounts (see environment variables for connection).")
    logger.info("Backend will be available at: http://localhost:%d", port)
    app.run(debug=debug, host='0.0.0.0', port=port)
