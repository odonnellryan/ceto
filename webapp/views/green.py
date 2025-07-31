from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json

import dataclasses
from green_scraper import (
    extract_text_from_pdf,
    extract_structured_data_from_pdf_text_via_ai,
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
        pdf_text = None
        parsed_items = []
        if form.file.data:
            filename = secure_filename(form.file.data.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            form.file.data.save(save_path)
            pdf_text = extract_text_from_pdf(save_path)
        text_source = form.manual_data.data or pdf_text
        if text_source:
            parsed_items = extract_structured_data_from_pdf_text_via_ai(text_source, filename or "manual")
        if not parsed_items:
            parsed_items = [None]

        for item in parsed_items:
            green = GreenData(
                filename=filename,
                manual_data=text_source,
                uploader=current_user,
            )
            if item:
                green.name = item.name
                green.url = item.url
                green.importer = item.importer
                green.farm = item.farm
                green.country = item.country
                green.arrival = item.arrival
                green.cupping_notes = item.cupping_notes
                green.variety = item.variety
                if item.quantity_available:
                    green.quantity_available = json.dumps([
                        dataclasses.asdict(q) for q in item.quantity_available
                    ])
                if item.size:
                    green.size_units = item.size.units
                    green.size_value = item.size.value
                if item.price:
                    green.price_units = item.price.units
                    green.price_value = item.price.value
                green.added = item.added
                green.removed = item.removed
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
