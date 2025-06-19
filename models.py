from extensions import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)

    performances = db.relationship('Performance', backref='user', lazy=True)
    quiz_attempts = db.relationship('UserQuiz', backref='user', lazy=True)
    quizzes = db.relationship('Quiz', backref='user', lazy=True)


class Chapters(db.Model):
    __tablename__ = 'chapters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(120), nullable=False)

    questions = db.relationship('Questions', backref='chapter', lazy=True)
    performances = db.relationship('Performance', backref='chapter', lazy=True)
    responses = db.relationship('UserResponse', backref='chapter', lazy=True)


class Questions(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_answer = db.Column(db.String(255), nullable=False)

    quiz_links = db.relationship('QuizQuestion', backref='question', lazy=True)
    user_responses = db.relationship('UserResponse', backref='question_obj', lazy=True)


class Quiz(db.Model):
    __tablename__ = 'quiz'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    duration = db.Column(db.String(120), nullable=False)
    remarks = db.Column(db.String(120))

    questions = db.relationship('QuizQuestion', backref='quiz', cascade='all, delete-orphan', lazy=True)
    user_attempts = db.relationship('UserQuiz', backref='quiz', lazy=True)


class QuizQuestion(db.Model):
    __tablename__ = 'quiz_question'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)


class UserQuiz(db.Model):
    __tablename__ = 'user_quiz'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    responses = db.relationship('UserResponse', backref='attempt', lazy=True)


class UserResponse(db.Model):
    __tablename__ = 'user_response'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('user_quiz.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    user_answer = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)

    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)


class Performance(db.Model):
    __tablename__ = 'performance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)

    easy_correct = db.Column(db.Integer, default=0)
    medium_correct = db.Column(db.Integer, default=0)
    hard_correct = db.Column(db.Integer, default=0)

    easy_total = db.Column(db.Integer, default=0)
    medium_total = db.Column(db.Integer, default=0)
    hard_total = db.Column(db.Integer, default=0)

    quiz = db.relationship('Quiz', backref=db.backref('performance', lazy=True))
