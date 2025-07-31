from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json

from green_scraper import (
    extract_text_from_pdf,
    extract_structured_data_from_pdf_text_via_ai,
    DataClassJSONEncoder,
)

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
        parsed_json = None
        pdf_text = None
        if form.file.data:
            filename = secure_filename(form.file.data.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            form.file.data.save(save_path)
            pdf_text = extract_text_from_pdf(save_path)
            if pdf_text:
                parsed_items = extract_structured_data_from_pdf_text_via_ai(pdf_text, filename)
                if parsed_items:
                    parsed_json = json.dumps(parsed_items, cls=DataClassJSONEncoder)
        green = GreenData(filename=filename,
                          manual_data=form.manual_data.data or pdf_text,
                          parsed_data=parsed_json,
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
