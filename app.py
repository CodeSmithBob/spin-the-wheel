from flask import Flask, request, redirect, url_for, render_template, jsonify
import sqlite3
import json
import uuid
from datetime import datetime, timedelta
import requests
import os
import sys

# Use /tmp directory for database (always writable in Docker)
DB_PATH = '/tmp/wheel_database.db'
SCHEMA_PATH = '/app/schema.sql'

# Initialize database BEFORE creating Flask app
def init_database():
    """Initialize the database with schema if it doesn't exist"""
    try:
        print(f"Checking database at {DB_PATH}...", flush=True)
        
        if not os.path.exists(DB_PATH):
            print(f"Creating database at {DB_PATH}...", flush=True)
            
            # Create database connection
            connection = sqlite3.connect(DB_PATH)
            
            # Read and execute schema
            print(f"Reading schema from {SCHEMA_PATH}...", flush=True)
            with open(SCHEMA_PATH, 'r') as f:
                schema = f.read()
                connection.executescript(schema)
            
            connection.commit()
            connection.close()
            print("✓ Database initialized successfully!", flush=True)
        else:
            print(f"✓ Database already exists at {DB_PATH}", flush=True)
            
    except Exception as e:
        print(f"✗ Error initializing database: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Don't exit - just log the error
        print("Continuing anyway...", flush=True)

# Initialize database before app creation
print("=" * 50, flush=True)
print("Starting Spin the Wheel Application", flush=True)
print("=" * 50, flush=True)
init_database()

# Create Flask app
app = Flask(__name__)
app.secret_key = "your_production_secret_key_change_this"

ADMIN_PASSWORD = "hamsilerziplayi"
DEFAULT_NAMES = ['Alice', 'Bob', 'Charlie', 'Diana']

def get_db_connection():
    """Create database connection with Row factory"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def get_client_ip():
    """Get client IP address from request"""
    if request.headers.get('CF-Connecting-IP'):
        return request.headers.get('CF-Connecting-IP')
    elif request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def get_country_from_ip(ip_address):
    """Get country from IP address using free geolocation API"""
    try:
        # Using ip-api.com (free, no key required, 45 req/min limit)
        response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('country', 'Unknown')
    except:
        pass
    return 'Unknown'

def track_visit(visit_type='homepage', wheel_id=None):
    """Track visitor information"""
    try:
        ip_address = get_client_ip()
        country = get_country_from_ip(ip_address)
        user_agent = request.headers.get('User-Agent', '')[:200]
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO visits (ip_address, country, user_agent, wheel_id, visit_type) VALUES (?, ?, ?, ?, ?)',
            (ip_address, country, user_agent, wheel_id, visit_type)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error tracking visit: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    """Homepage - Create new wheel or load existing"""
    track_visit('homepage')
    
    if request.method == 'POST':
        names = request.form.getlist('names[]')
        names = [n.strip() for n in names if n.strip()]
        
        if not names:
            names = DEFAULT_NAMES
        
        # Generate unique ID
        unique_id = str(uuid.uuid4())[:8]
        
        # Get creator's country
        ip_address = get_client_ip()
        creator_country = get_country_from_ip(ip_address)
        
        # Save to database with creator country
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO wheels (unique_id, names, name_count, creator_country) VALUES (?, ?, ?, ?)',
            (unique_id, json.dumps(names), len(names), creator_country)
        )
        conn.commit()
        conn.close()
        
        track_visit('wheel_created', unique_id)
        
        # Fixed: use unique_id instead of wheel_id
        return redirect(url_for('wheel', wheel_id=unique_id))
    
    return render_template('index.html', default_names=DEFAULT_NAMES)



@app.route('/wheel/<wheel_id>', methods=['GET', 'POST'])
def wheel(wheel_id):
    """Wheel page - Display and update wheel"""
    conn = get_db_connection()
    
    # Get wheel data
    wheel_data = conn.execute(
        'SELECT * FROM wheels WHERE unique_id = ?',
        (wheel_id,)
    ).fetchone()
    
    if not wheel_data:
        conn.close()
        return redirect(url_for('index'))
    
    # Update last accessed time
    conn.execute(
        'UPDATE wheels SET last_accessed = CURRENT_TIMESTAMP WHERE unique_id = ?',
        (wheel_id,)
    )
    conn.commit()
    
    names = json.loads(wheel_data['names'])
    
    if request.method == 'POST':
        # Update names
        new_names = request.form.getlist('names[]')
        new_names = [n.strip() for n in new_names if n.strip()]
        
        if new_names:
            conn.execute(
                'UPDATE wheels SET names = ?, name_count = ?, last_accessed = CURRENT_TIMESTAMP WHERE unique_id = ?',
                (json.dumps(new_names), len(new_names), wheel_id)
            )
            conn.commit()
            names = new_names
    
    conn.close()
    track_visit('wheel_access', wheel_id)
    
    return render_template('wheel.html', names=names, wheel_id=wheel_id)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Admin dashboard with statistics"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password != ADMIN_PASSWORD:
            return render_template('admin.html', error="Invalid password", authenticated=False)
        
        # Get statistics
        conn = get_db_connection()
        
        # Total visitors
        total_visitors = conn.execute('SELECT COUNT(DISTINCT ip_address) FROM visits').fetchone()[0]
        
        # Total visits
        total_visits = conn.execute('SELECT COUNT(*) FROM visits').fetchone()[0]
        
        # Visitors in last 30 days
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        visitors_30_days = conn.execute(
            'SELECT COUNT(DISTINCT ip_address) FROM visits WHERE visited_at >= ?',
            (thirty_days_ago,)
        ).fetchone()[0]
        
        # Total wheels created
        total_wheels = conn.execute('SELECT COUNT(*) FROM wheels').fetchone()[0]
        
        # Recent wheels (top 50)
        recent_wheels = conn.execute('''
            SELECT 
                w.unique_id,
                w.names,
                w.name_count,
                w.creator_country,
                w.created_at,
                w.last_accessed,
                COUNT(DISTINCT v.ip_address) as visitor_count
            FROM wheels w
            LEFT JOIN visits v ON w.unique_id = v.wheel_id
            GROUP BY w.id
            ORDER BY w.created_at DESC
            LIMIT 50
        ''').fetchall()
        
        # Visits by country
        country_stats = conn.execute('''
            SELECT country, COUNT(*) as count
            FROM visits
            GROUP BY country
            ORDER BY count DESC
            LIMIT 20
        ''').fetchall()
        
        conn.close()
        
        return render_template(
            'admin.html',
            authenticated=True,
            total_visitors=total_visitors,
            total_visits=total_visits,
            visitors_30_days=visitors_30_days,
            total_wheels=total_wheels,
            recent_wheels=recent_wheels,
            country_stats=country_stats
        )
    
    return render_template('admin.html', authenticated=False)

@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
