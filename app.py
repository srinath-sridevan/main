from flask import Flask, request, send_file, redirect, url_for, render_template
import os
from cryptography.fernet import Fernet
from io import BytesIO
import json
import datetime
from flask import session


app = Flask(__name__)

# Secret key for session-based messages
app.secret_key = 'your_secret_key'  # Change this for security purposes

# Set upload folder and max content length (100 MB)
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

# Store file metadata outside of the uploads directory
METADATA_FOLDER = os.path.join(app.root_path, 'metadata')
os.makedirs(METADATA_FOLDER, exist_ok=True)
METADATA_FILE = os.path.join(METADATA_FOLDER, 'file_metadata.json')

# File type categorization based on extensions
FILE_CATEGORIES = {
    'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.jfif'],
    'Documents': ['.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.csv','.doc'],
    'Audio': ['.mp3', '.wav', '.aac', '.flac'],
    'Videos': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
    'Archives': ['.zip', '.tar', '.gz', '.rar'],
    'Software & Apps': ['.exe', '.apk'],
    'Others': []
}

# Encryption setup
def load_key():
    return open('secret.key', 'rb').read()

fernet = Fernet(load_key())

# Function to classify file based on its extension
def classify_file(filename):
    file_ext = os.path.splitext(filename)[1].lower()
    for category, extensions in FILE_CATEGORIES.items():
        if file_ext in extensions:
            return category
    return 'Others'  # Default category if no match is found

# Function to save username and pin with file metadata
def save_metadata(filename, username, pin):
    metadata = {
        'username': username.upper(),  # Ensure the username is in uppercase
        'pin': pin if pin else None,  # Store None if no pin is provided
        'category': classify_file(filename),
        'upload_time': datetime.datetime.now().isoformat()
    }
    
    # Load existing metadata if available
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            file_metadata = json.load(f)
    else:
        file_metadata = {}

    # Add new metadata for the uploaded file
    file_metadata[filename] = metadata
    
    # Save updated metadata
    with open(METADATA_FILE, 'w') as f:
        json.dump(file_metadata, f, indent=4)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Handle file uploads
        files = request.files.getlist('file')  # Handle multiple files
        username = request.form.get('username')
        pin = request.form.get('pin')  # PIN is optional
        
        for uploaded_file in files:
            if uploaded_file and uploaded_file.filename:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
                data = uploaded_file.read()
                encrypted_data = fernet.encrypt(data)
                with open(filepath, 'wb') as f:
                    f.write(encrypted_data)
                print(f"File uploaded: {uploaded_file.filename}")  # Debugging line

                # Save file metadata (username, pin, category)
                save_metadata(uploaded_file.filename, username, pin)

        return redirect(url_for('upload_file'))

    # List files in the uploads folder
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    print(f"Files in upload folder: {files}")  # Debugging line

    # Filter out non-file items (e.g., directories, metadata files)
    files = [file for file in files if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], file))]
    print(f"Filtered files: {files}")  # Debugging line

    # Sort files by modification time (descending order)
    sorted_files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), reverse=True)
    print(f"Sorted files: {sorted_files}")  # Debugging line

    # Classify files into categories
    categorized_files = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            file_metadata = json.load(f)
        
        for file in sorted_files:
            metadata = file_metadata.get(file, {})
            category = metadata.get('category', 'Others')
            if category not in categorized_files:
                categorized_files[category] = []
            categorized_files[category].append({
                'filename': file,
                'extension': os.path.splitext(file)[1],
                'username': metadata.get('username', 'Unknown'),
                'pin': metadata.get('pin', None)
            })

    return render_template('index.html', categorized_files=categorized_files)

@app.route('/uploads/<filename>')
def download_file(filename):
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            file_metadata = json.load(f)
        file_data = file_metadata.get(filename, {})
        pin_required = file_data.get('pin')

        if pin_required and not session.get(f'pin_verified_{filename}'):
            return redirect(url_for('pin_prompt', filename=filename))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    return send_file(BytesIO(decrypted_data), as_attachment=True, download_name=filename)

@app.route('/pin_prompt/<filename>', methods=['GET', 'POST'])
def pin_prompt(filename):
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            file_metadata = json.load(f)
        file_data = file_metadata.get(filename, {})
        pin_required = file_data.get('pin')

        if pin_required:
            if request.method == 'POST':
                entered_pin = request.form.get('pin')
                if entered_pin == file_data['pin']:
                    session[f'pin_verified_{filename}'] = True  # Store pin verification
                    return redirect(url_for('download_file', filename=filename))
                else:
                    return render_template('pin_prompt.html', filename=filename, error="Incorrect PIN, please try again.")
            return render_template('pin_prompt.html', filename=filename)

    return "File not found or not private.", 404

if __name__ == '__main__':
    app.run(debug=True)
