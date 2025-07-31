from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from .. import db
from ..models import GreenData, TastingNote
from ..forms import GreenUploadForm, TastingNoteForm


green_bp = Blueprint('green', __name__, url_prefix='/green')
UPLOAD_FOLDER = 'uploads'


def ensure_upload_folder():
    os.makedirs(os.path.join(os.getcwd(), UPLOAD_FOLDER), exist_ok=True)


@green_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_green():
    form = GreenUploadForm()
    ensure_upload_folder()
    if form.validate_on_submit():
        filename = None
        if form.file.data:
            filename = secure_filename(form.file.data.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            form.file.data.save(save_path)
        green = GreenData(filename=filename,
                          manual_data=form.manual_data.data,
                          uploader=current_user)
        db.session.add(green)
        db.session.commit()
        flash('Green data uploaded.', 'success')
        return redirect(url_for('main.index'))
    return render_template('upload.html', form=form)


@green_bp.route('/<int:green_id>', methods=['GET', 'POST'])
@login_required
def green_detail(green_id):
    green = GreenData.query.get_or_404(green_id)
    form = TastingNoteForm()
    if form.validate_on_submit():
        note = TastingNote(user_id=current_user.id,
                           green_data_id=green.id,
                           notes=form.notes.data)
        db.session.add(note)
        db.session.commit()
        flash('Tasting note added.', 'success')
        return redirect(url_for('green.green_detail', green_id=green.id))
    return render_template('green_detail.html', green=green, form=form)
