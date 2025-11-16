import sqlite3

def init_database():
    """Initialize the database with schema"""
    connection = sqlite3.connect('wheel_database.db')
    
    with open('schema.sql') as f:
        connection.executescript(f.read())
    
    connection.commit()
    connection.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()
