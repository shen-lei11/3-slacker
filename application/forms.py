from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    FloatField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=4, max=128)])
    submit = SubmitField("Sign In")


class TaskForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1200)])
    status = SelectField(
        "Status",
        choices=[("todo", "To Do"), ("doing", "In Progress"), ("done", "Done")],
        validators=[DataRequired()],
    )
    priority = SelectField(
        "Priority",
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        validators=[DataRequired()],
    )
    deadline = DateField("Deadline", validators=[Optional()])
    user_id = SelectField("Owner", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Save Task")


class CurrentFocusForm(FlaskForm):
    user_id = SelectField("Person", coerce=int, validators=[DataRequired()])
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1200)])
    status_note = StringField("Status Note", validators=[Optional(), Length(max=160)])
    target_date = DateField("Target Date", validators=[Optional()])
    submit = SubmitField("Save Focus")


class BacklogForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1200)])
    category = SelectField(
        "Category",
        choices=[("shared", "Shared"), ("personal", "Personal"), ("someday", "Someday")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save Item")


class AchievementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1200)])
    user_id = SelectField("Person", coerce=int, validators=[DataRequired()])
    date_achieved = DateField("Date Achieved", validators=[DataRequired()])
    submit = SubmitField("Post Achievement")


class JarEntryForm(FlaskForm):
    user_id = SelectField("Fined Person", coerce=int, validators=[DataRequired()])
    reason = StringField("Reason", validators=[DataRequired(), Length(max=200)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=1.0, max=9999.0)])
    submit = SubmitField("Add Fine")
