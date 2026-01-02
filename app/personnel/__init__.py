# app/personnel/__init__.py
from flask import Blueprint

bp = Blueprint('personnel', __name__)

from app.personnel import routes