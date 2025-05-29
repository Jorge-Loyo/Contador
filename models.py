from app import db # Importa la instancia 'db' que creaste en app.py

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False) # Opcional, pero común
    password_hash = db.Column(db.String(128), nullable=False) # Para la contraseña hasheada

    def __repr__(self):
        return f'<User {self.username}>'