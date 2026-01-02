from flask import Blueprint

# 'auth' adında bir modül oluşturuyoruz
bp = Blueprint('auth', __name__)

# Rotaları (sayfaları) içeri aktar
from app.auth import routes