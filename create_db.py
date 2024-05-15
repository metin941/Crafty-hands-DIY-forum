from app import app, db
from app import User, Thread  # Import your SQLAlchemy models

def create_or_update_database():
    # Create an application context
    with app.app_context():
        # Create all tables
        db.drop_all()
        db.create_all()

if __name__ == "__main__":
    create_or_update_database()
