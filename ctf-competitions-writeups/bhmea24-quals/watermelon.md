# Watermelon

I will list here the functions and classes that might be interesting for us :

**Path of the database & File Class**

{% code title="app.py" lineNumbers="true" %}
```py
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secrets.token_hex(20)
app.config['UPLOAD_FOLDER'] = 'files'


db = SQLAlchemy(app)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('files', lazy=True))
```
{% endcode %}

**Admin check**

{% code title="app.py" %}
```py
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or 'user_id' not in session or not session['username']=='admin':
            return jsonify({"Error": "Unauthorized access"}), 401
        return f(*args, **kwargs)
    return decorated_function
```
{% endcode %}

**Upload function**

{% code title="app.py" %}
```py
@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"Error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"Error": "No selected file"}), 400
    
    user_id = session.get('user_id')
    if file:
        blocked = ["proc", "self", "environ", "env"]
        filename = file.filename

        if filename in blocked:
            return jsonify({"Error":"Why?"})

        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, filename)

        file.save(f"{user_dir}/{secure_filename(filename)}")
        

        new_file = File(filename=secure_filename(filename), filepath=file_path, user_id=user_id)
        db.session.add(new_file)
        db.session.commit()
        
        return jsonify({"Message": "File uploaded successfully", "file_path": file_path}), 201

    return jsonify({"Error": "File upload failed"}), 500
```
{% endcode %}

**File view function**

{% code title="app.py" %}
```py
@app.route("/file/<int:file_id>", methods=["GET"])
@login_required  
def view_file(file_id):
    user_id = session.get('user_id')
    file = File.query.filter_by(id=file_id, user_id=user_id).first()

    if file is None:
        return jsonify({"Error": "File not found or unauthorized access"}), 404
    
    try:
        return send_file(file.filepath, as_attachment=True)
    except Exception as e:
        return jsonify({"Error": str(e)}), 500
```
{% endcode %}

**Flag print**

{% code title="app.py" %}
```py
@app.get('/admin')
@admin_required
def admin():
    return os.getenv("FLAG","BHFlagY{testing_flag}")
```
{% endcode %}

So basically this app doesn't have UI, you need to register using burp or curl, then login and upload a file.

But where is the vulnerability? We can only read the flag if we somehow read the environment variable `FLAG` or by going to admin page.

Looking at these few lines in the upload function :

<pre class="language-py" data-title="app.py"><code class="lang-py">        user_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
<strong>        file_path = os.path.join(user_dir, filename)
</strong>
        file.save(f"{user_dir}/{secure_filename(filename)}")
        

        new_file = File(filename=secure_filename(filename), filepath=file_path, user_id=user_id)
        db.session.add(new_file)
        db.session.commit()
</code></pre>

Firstly, a `user_dir` is created with our id in the upload folder which is `files` so `files/2`.

then it calls the `os.path.join` to join the `user_dir` directory with our file name and put it in `file_path` variable.

Then it inserts `file_path` in the database.

We can also access it with its `id` in the database as stated in File view func :

{% code title="app.py" %}
```py
@app.route("/file/<int:file_id>", methods=["GET"])
@login_required  
def view_file(file_id):
    user_id = session.get('user_id')
    file = File.query.filter_by(id=file_id, user_id=user_id).first()

    if file is None:
        return jsonify({"Error": "File not found or unauthorized access"}), 404
    
    try:
        return send_file(file.filepath, as_attachment=True)
    except Exception as e:
        return jsonify({"Error": str(e)}), 500
```
{% endcode %}

Taking a look at [`os.path.join`](https://docs.python.org/3/library/os.path.html#os.path.join) documentation :

> If a segment is an absolute path (which on Windows requires both a drive and a root), then all previous segments are ignored and joining continues from the absolute path segment.

So if we uploaded our file with a name like : `/etc/passwd`

the `os.path.join` function will ignore the `files/2` and upload our file with the same name.

Great, let's do it :

![Screenshot (193)](<../../.gitbook/assets/7212c83c 830e 4e3c a0f2 da31b6bf10b8>)

And we got it :

![Screenshot (196)](<../../.gitbook/assets/d7e5614f 6ac8 443a b93b eb467a267b79>)

Now how do we get the flag? There are many ways to get it.

Examples:

{% stepper %}
{% step %}
**Read process environment**

Set the filename to /proc/1/environ and download it.

![Screenshot (197)](<../../.gitbook/assets/277b0df8 92f6 44c3 9a14 a77f8cab0698>)

You can retrieve the flag from the environment contents.

![Screenshot (198)](<../../.gitbook/assets/fb8fc164 d328 4707 b502 2c3e3d00a87f>)
{% endstep %}

{% step %}
**Download the SQLite DB**

Set the filename to /app/instance/db.db, then download the DB and open it with any DB viewer to get the admin password. Use that to access /admin.

![Screenshot (199)](<../../.gitbook/assets/c653bb83 a06c 4f6e a3b0 2bd837cf7e13>)

![Screenshot (200)](<../../.gitbook/assets/cbede92c 04ba 4c66 adb9 bd953b3139a2>)
{% endstep %}

{% step %}
**Read source file and secret key**

Set the filename to /app/app.py and read the `SECRET_KEY`. With that you can create your own admin cookie using tools like `flask-unsign` and access /admin.
{% endstep %}
{% endstepper %}
