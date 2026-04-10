from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


TASK_STATUS_CHOICES = [("To Do", "To Do"), ("In Progress", "In Progress"), ("Done", "Done")]
TASK_PRIORITY_CHOICES = [("Low", "Low"), ("Medium", "Medium"), ("High", "High")]
BACKLOG_CATEGORY_CHOICES = [
    ("Project", "Project"),
    ("Habit", "Habit"),
    ("Business", "Business"),
    ("Learning", "Learning"),
    ("Other", "Other"),
]


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class TaskForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional()])
    status = SelectField("Status", choices=TASK_STATUS_CHOICES, validators=[DataRequired()])
    priority = SelectField("Priority", choices=TASK_PRIORITY_CHOICES, validators=[DataRequired()])
    deadline = DateField("Deadline", validators=[Optional()])
    submit = SubmitField("Save Task")


class CurrentFocusForm(FlaskForm):
    title = StringField("What are you focused on?", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional()])
    status_note = StringField("Status Note", validators=[Optional(), Length(max=255)])
    target_date = DateField("Target Date", validators=[Optional()])
    submit = SubmitField("Save Focus")


class BacklogForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional()])
    category = SelectField("Category", choices=BACKLOG_CATEGORY_CHOICES, validators=[DataRequired()])
    submit = SubmitField("Save Backlog Item")


class AchievementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional()])
    date_achieved = DateField("Date Achieved", validators=[DataRequired()], default=date.today)
    submit = SubmitField("Save Achievement")


class SlackingJarForm(FlaskForm):
    user_id = SelectField("User", coerce=int, validators=[DataRequired()])
    reason = StringField("Reason", validators=[DataRequired(), Length(max=255)])
    amount = DecimalField(
        "Amount ($)",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01, message="Amount must be positive")],
        default=1.00,
    )
    is_paid = BooleanField("Paid")
    issued_by = SelectField("Issued By", coerce=int, validators=[DataRequired()])
    date_issued = DateField("Date Issued", validators=[DataRequired()], default=date.today)
    submit = SubmitField("Save Fine")
