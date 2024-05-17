from flask import Flask, render_template, request, redirect, url_for, flash,jsonify,Response
from flask_sqlalchemy import SQLAlchemy
from flask import session
import os
from werkzeug.utils import secure_filename
import logging
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'Secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['UPLOAD_DIR'] = 'static\images'  # Set the upload directory path for render.com to store images need premium plan with disk space (https://render.com/docs/disks) 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)
# Ensure the upload directory exists
if not os.path.exists(app.config['UPLOAD_DIR']):
    os.makedirs(app.config['UPLOAD_DIR'])

logging.basicConfig(level=logging.DEBUG)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    country = db.Column(db.String(120), nullable=False)
    last_activity = db.Column(db.DateTime, default=db.func.current_timestamp())

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('threads', lazy=True))

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.id'), nullable=False)
    thread = db.relationship('Thread', backref=db.backref('responses', lazy=True))

class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(120), nullable=False)
    user_agent = db.Column(db.String(200), nullable=False)
    page_visited = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

#ADMIN PAGE PART ---------------------------------------------
@app.before_request
def log_request_info():
    visitor_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    page_visited = request.path
    app.logger.info(f"Visitor IP: {visitor_ip}, User-Agent: {user_agent}, Page Visited: {page_visited}")

    # Save visitor info to the database
    visitor = Visitor(ip_address=visitor_ip, user_agent=user_agent, page_visited=page_visited)
    db.session.add(visitor)
    db.session.commit()

    # Update the last_activity for the logged-in user
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.last_activity = datetime.utcnow()
            db.session.commit()

@app.route('/visitors')
def view_visitors():
    visitors = Visitor.query.all()
    online_users = get_online_users()  # Get online users
    return render_template('visitors.html', visitors=visitors, online_users=online_users)  # Pass online_users to the template

def get_online_users():
    now = datetime.utcnow()
    five_minutes_ago = now - timedelta(minutes=5)
    online_users = User.query.filter(User.last_activity >= five_minutes_ago).all()
    return online_users

@app.route('/online_users')
def online_users():
    ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
    online_users = User.query.filter(User.last_activity >= ten_minutes_ago).all()
    return render_template('online_users.html', users=online_users)

#------------------------------------------------------------------

@app.route('/')
def index():
    username = None
    threads = None
    query = request.args.get('query')
    if query:
        # If a search query is provided, display search results
        threads = Thread.query.filter(Thread.title.ilike(f'%{query}%')).all()
    else:
        # If no search query is provided, display all threads
        threads = Thread.query.all()

    if 'user_id' in session:
        user_id = session['user_id']
        user = User.query.get(user_id)
        if user:
            username = user.username

    return render_template('index.html', threads=threads, username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id  # Store the user's ID in the session
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/create_thread', methods=['GET', 'POST'])
def create_thread():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        if 'user_id' in session:
            user_id = session['user_id']
            thread = Thread(title=title, content=content, user_id=user_id)
            db.session.add(thread)
            db.session.commit()
            # Redirect to the route for viewing the newly created thread
            return redirect(url_for('view_thread', thread_id=thread.id))
        else:
            return redirect(url_for('login'))
    return render_template('create_thread.html')

@app.route('/thread/<int:thread_id>')
def view_thread(thread_id):
    thread = db.session.query(Thread).get(thread_id)
    if thread:
        # Pass the thread and its content to the template
        return render_template('thread.html', thread=thread)
    else:
        return "Thread not found", 404

@app.route('/edit_thread/<int:thread_id>', methods=['GET', 'POST'])
def edit_thread(thread_id):
    if 'user_id' in session:
        user_id = session['user_id']
        thread = Thread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread:
            if request.method == 'POST':
                thread.title = request.form['title']
                thread.content = request.form['content']
                db.session.commit()
                return redirect(url_for('index'))
            else:
                return render_template('edit_thread.html', thread=thread)
        else:
            return "You don't have permission to edit this thread."
    else:
        return redirect(url_for('login'))

@app.route('/update_thread/<int:thread_id>', methods=['POST'])
def update_thread(thread_id):
    if 'user_id' in session:
        user_id = session['user_id']
        thread = Thread.query.filter_by(id=thread_id, user_id=user_id).first()
        if thread:
            if request.method == 'POST':
                # Get the updated title and content from the form
                updated_title = request.form['title']
                updated_content = request.form['content']
                
                # Update the thread's attributes
                thread.title = updated_title
                thread.content = updated_content
                
                # Commit the changes to the database
                db.session.commit()
                
                # Redirect to the homepage after updating the thread
                return redirect(url_for('index'))
            else:
                # Render the edit thread form
                return render_template('edit_thread.html', thread=thread)
        else:
            return "You don't have permission to edit this thread."
    else:
        return redirect(url_for('login'))

@app.route('/delete_thread/<int:thread_id>', methods=['GET', 'POST'])
def delete_thread(thread_id):
    if 'user_id' in session:
        thread = Thread.query.get(thread_id)
        if thread:
            # Delete associated responses first
            Response.query.filter_by(thread_id=thread_id).delete()
            
            # Now delete the thread
            db.session.delete(thread)
            db.session.commit()
            return redirect(url_for('index'))  # Redirect to the index page after deleting the thread
        else:
            return "Thread not found", 404
    else:
        return redirect(url_for('login'))

@app.route('/add_response/<int:thread_id>', methods=['POST'])
def add_response(thread_id):
    if 'user_id' in session:
        response_content = request.form['response_content']

        thread = Thread.query.get(thread_id)

        if thread:
            response = Response(content=response_content)
            thread.responses.append(response)
            db.session.commit()
            return redirect(url_for('view_thread', thread_id=thread_id))
        else:
            return "Thread not found", 404
    else:
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        email = request.form['email']
        country = request.form['country']
        
        # Check if the username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already taken. Please choose a different one.', 'error')
            if existing_user.email == email:
                flash('Email already taken. Please use a different one.', 'error')
        else:
            # Create a new user
            new_user = User(username=username, password=password, name=name, email=email, country=country)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))

    return render_template('register.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_image', methods=['POST'])
def upload_image():
    app.logger.debug('Upload image request received')

    if 'file' not in request.files:
        app.logger.error('No file part in request')
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']

    if file.filename == '':
        app.logger.error('No selected file')
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_DIR'], filename)
        app.logger.debug(f'Saving file to {file_path}')
        file.save(file_path)
        uploaded_image_url = url_for('static', filename=f'images/{filename}')
        app.logger.debug(f'File saved, URL is {uploaded_image_url}')
        return jsonify({'url': uploaded_image_url}), 200
    else:
        app.logger.error('Invalid file type')
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/search_threads', methods=['GET','POST'])
def search_threads():
    query = request.args.get('query')
    if query:
        # Perform a search for threads based on the query
        threads = Thread.query.filter(Thread.title.ilike(f'%{query}%')).all()
        return render_template('search_results.html', threads=threads, query=query)
    else:
        # If no query is provided, redirect back to the index page
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
