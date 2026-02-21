from flask import Flask, request, jsonify, session
from flask_cors import CORS
from models import db, User, Bill
from werkzeug.security import generate_password_hash, check_password_hash
import os

from datetime import timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key' # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rupeeflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}, origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:5000", "http://localhost:5000", "http://0.0.0.0:5500", "http://0.0.0.0:5000"])
db.init_app(app)

with app.app_context():
    db.create_all()

def calculate_user_logic(user):
    total = user.want + user.need + user.savings
    if total == 0:
        return 100, 1, "Welcome! Start adding bills to track your financial health." # Default score and level 1
    
    need_pct = (user.need / total) * 100
    want_pct = (user.want / total) * 100
    save_pct = (user.savings / total) * 100
    
    error = abs(need_pct - 50) + abs(want_pct - 30) + abs(save_pct - 20)
    score = int(max(0, 100 - error))
    
    # Level logic: 40=1, 45=2, 55=3, 65=4...
    if score < 45:
        level = 1
    else:
        level = 2 + (score - 45) // 10
        
    # Drop penalty: if current score is 10 < than last month, decrease to last level
    if score < (user.last_month_points - 10):
        level = user.last_month_level
        
    feedback = "Keep going! Small steps lead to big savings."
    if level > user.level:
        feedback = f"Amazing! You've reached Level {level}. Your financial discipline is paying off!"
    elif level < user.level:
        feedback = "Level dropped. It's okay! Focus on the 50-30-20 rule to climb back up. You can do it!"
    elif score > user.points:
        feedback = "Nice! Your score improved. You're getting closer to the ideal 50-30-20 balance."
    elif score < user.points:
         feedback = "Score dipped slightly. Try to increase your savings or reduce wants to stay on track!"
        
    return score, level, feedback

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 400

    new_user = User(username=username, password=generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    session.permanent = True
    session['user_id'] = user.id
    return jsonify({
        'message': 'Logged in successfully',
        'username': user.username,
        'id': user.id
    }), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/user/data', methods=['GET'])
def get_user_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Unauthorized'}), 401

    user = User.query.get(user_id)
    history = []
    for bill in user.bills:
        history.append({
            'id': bill.bill_id,
            'amount': bill.amount,
            'category': bill.category,
            'date': bill.date.strftime('%d %b'),
            'image_url': bill.image_url
        })

    return jsonify({
        'username': user.username,
        'want': user.want,
        'need': user.need,
        'savings': user.savings,
        'points': user.points,
        'level': user.level,
        'history': history
    }), 200

@app.route('/api/bill', methods=['POST'])
def add_bill():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.json
    amount = data.get('amount')
    category = data.get('category') # 'want', 'need', 'save'
    image_url = data.get('image_url')
    
    if not amount or not category:
        return jsonify({'message': 'Amount and category required'}), 400

    # Map 'save' to 'savings' if needed to match frontend
    if category == 'save':
        category = 'savings'

    user = User.query.get(user_id)
    
    # Simple incremented ID for the bill as requested
    max_bill_id = db.session.query(db.func.max(Bill.bill_id)).scalar() or 0
    next_bill_id = max_bill_id + 1

    new_bill = Bill(
        bill_id=next_bill_id,
        amount=amount,
        category=category,
        image_url=image_url,
        user_id=user.id
    )

    # Update user totals
    if category == 'want':
        user.want += amount
    elif category == 'need':
        user.need += amount
    elif category == 'savings':
        user.savings += amount

    # Recalculate score and level
    user.points, user.level, feedback = calculate_user_logic(user)

    db.session.add(new_bill)
    db.session.commit()

    return jsonify({
        'message': 'Bill added successfully',
        'bill_id': next_bill_id,
        'user_totals': {
            'want': user.want,
            'need': user.need,
            'savings': user.savings,
            'points': user.points,
            'level': user.level,
            'feedback': feedback
        }
    }), 201

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    if file:
        filename = f"{os.urandom(8).hex()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'url': f'/uploads/{filename}'}), 200

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=process.env.PORT or 5000)

@app.route('/')
def home():
    return render_template('index.html')
