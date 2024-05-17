from flask import Flask, render_template, request, redirect, url_for, flash,jsonify,Response
from flask_sqlalchemy import SQLAlchemy
from flask import session
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'Secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['UPLOAD_DIR'] = 'static\images'  # Set the upload directory path
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    country = db.Column(db.String(120), nullable=False)

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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']

    # Check if the file is empty
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Check if the file has an allowed extension
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_DIR'], filename))
        # Construct the URL for the uploaded image
        uploaded_image_url = url_for('static', filename='images/' + filename)
        return jsonify({'url': uploaded_image_url}), 200
    else:
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
