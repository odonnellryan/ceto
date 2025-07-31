from flask import Blueprint, render_template
from flask_login import login_required

from ..models import GreenData

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    greens = GreenData.query.order_by(GreenData.created_at.desc()).all()
    return render_template('index.html', greens=greens)
