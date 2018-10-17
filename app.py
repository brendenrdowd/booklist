from flask import Flask,render_template,flash,redirect,url_for,session,logging,request
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

app =  Flask(__name__)

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_DB'] = 'booklist'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.secret_key = 'aksjdfhaskjdf'

# init MySQL
mysql = MySQL(app)

class RegisterForm(Form):
    fname = StringField('First Name',[validators.Length(min=1,max=50)])
    lname = StringField('Last Name',[validators.Length(min=1,max=50)])
    email = StringField('Email',[validators.Length(min=6,max=50)])
    password = PasswordField('Password',[
        validators.DataRequired(),
        validators.EqualTo('confirm',message="Passwords do not match")
    ])
    confirm = PasswordField('Confirm Password')

@app.route('/')
def home():
    form = RegisterForm(request.form)
    return render_template('home.html',form=form)

# User Routes

@app.route('/register',methods=['POST'])
def register():
    form = RegisterForm(request.form)
    if form.validate():
        fname = form.fname.data
        lname = form.lname.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # check for pre-existing email
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM users WHERE email = %s ",[email])
        if result >0:
            flash('Email already exists', 'danger')
            return redirect(url_for('home'))

        cur.execute("INSERT INTO users(fname,lname,email,password) VALUES (%s,%s,%s,%s)", (fname,lname,email,password))

        # Commit to DB
        mysql.connection.commit()

        # Close Connection
        cur.close()
        flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    else:
        flash('Invalid Entry, please recheck fields', 'danger')
        return redirect(url_for('home'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        email = request.form['email']
        password_candidate = request.form['password']
        
        # Create Cursor
        cur = mysql.connection.cursor()

        # Get by Email
        result = cur.execute("SELECT * FROM users WHERE email = %s", [email])
        if result > 0:
            # Get Stored Hash
            data = cur.fetchone()
            password = data['password']
            name = data['fname']
            id = data['id']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate,password):
                # passed
                session['logged_in'] = True
                session['name'] = name.capitalize()
                session['uid'] = id
                flash('You are now logged in','success')
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid login"
                return render_template('login.html', error=error)
            cur.close()
        else:
            error = "email not found"
            return render_template('login.html', error=error)
    return render_template('login.html')

# Authentication
def is_logged_in(f):
    @wraps(f)
    def wrap(*args,**kwargs):
        if 'logged_in' in session:
            return f(*args,**kwargs)
        else:
            flash('Unauthorized, please log in','danger')
            return redirect(url_for('login'))
    return wrap
    
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out','success')
    return redirect(url_for('login'))

# Book routes
@app.route('/dashboard')
@is_logged_in
def dashboard():
    cur = mysql.connection.cursor()
    # get books on user's list
    results = cur.execute("SELECT * FROM list WHERE user_id = %s",[session['uid']])
    mylist = cur.fetchall()
    if results > 0:
        books = []
        for book in mylist:
            cur.execute("SELECT * FROM books WHERE id = %s",[book['book_id']])
            books.append(cur.fetchone())
        return render_template('dashboard.html',books=books)
    else:
        msg = "No books Found"
        return render_template('dashboard.html',msg=msg)
    cur.close()

@app.route('/books')
def books():
    cur = mysql.connection.cursor()
    results = cur.execute("SELECT * FROM books")
    books = cur.fetchall()
    if results > 0:
        return render_template('books.html',books=books)
    else:
        msg = "No books Found"
        return render_template('books.html',msg=msg)
    cur.close()

@app.route('/search',methods=['POST','GET'])
def search():
    keyword = request.form['keyword']
    cur = mysql.connection.cursor()
    results = cur.execute("SELECT * FROM books WHERE(title LIKE %s OR author LIKE %s OR isbn LIKE %s)", (keyword,keyword,keyword)) # ew
    books = cur.fetchall()
    if results > 0:
        return render_template('books.html',books=books)
    else:
        msg = "No books Found"
        return render_template('books.html',msg=msg)
    cur.close()


class BookForm(Form):
    title = StringField('Title',[validators.Length(min=3,max=50)])
    author = StringField('Author',[validators.Length(min=1,max=50)])
    isbn = StringField('ISBN',[validators.Regexp('^(97(8|9))?\d{9}(\d|X)$')])

@app.route('/addBook',methods=['POST','GET'])
@is_logged_in
def addBook():
    form = BookForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        author = form.author.data
        isbn = form.isbn.data

        cur = mysql.connection.cursor()
        # Check for duplicates
        results = cur.execute("SELECT * FROM books WHERE isbn = %s",[isbn])
        if results > 0:
            flash('Book Already Exists','danger')
            return redirect(url_for('books'))
        cur.execute("INSERT INTO books(title,author,isbn) VALUES(%s,%s,%s)",(title,author,isbn))
        mysql.connection.commit()
        cur.close()
        flash('Book Added','success')
        return redirect(url_for('books'))
    else:
        app.logger.info("ERROR")
    return render_template('create.html',form=form)

@app.route('/addToList/<string:id>',methods=['POST'])
@is_logged_in
def addToList(id):
        cur = mysql.connection.cursor()
        # Check for duplicates
        results = cur.execute("SELECT * FROM list WHERE book_id = %s",[id])
        if results > 0:
            flash('Book Already In List','danger')
            return redirect(url_for('books'))
        cur.execute("INSERT INTO list(book_id,user_id) VALUES(%s,%s)",(id,session['uid']))
        mysql.connection.commit()
        cur.close()
        flash('Book added to your Reading List','success')
        return redirect(url_for('dashboard'))

@app.route('/remove/<string:id>',methods=["POST"])
@is_logged_in
def remove(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM list WHERE book_id = %s", [id])
    mysql.connection.commit()
    cur.close()
    flash('Book Removed','success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)