from flask import Flask, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime, timezone, timedelta
import random
from quiz_selector import generate_adaptive_quiz 
from functools import wraps
from quiz_env import QuizEnv
from dqn_agent import DQNAgent


app = Flask(__name__)
app.secret_key = 'MyProject'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'quiz.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

CORS(app, supports_credentials=True, origins=["*"])

from models import User, Chapters, QuizQuestion, Quiz, UserResponse, Performance, UserQuiz, Questions

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify(success=True, user_id=user.id, is_admin=user.is_admin)
    else:
        return jsonify(success=False, message="Invalid credentials"), 401


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    fullname = data.get('fullname')
    dob = data.get('dob')
    is_admin = data.get('is_admin', False)

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already registered"}), 400

    new_user = User(
        email=email,
        password=generate_password_hash(password),
        fullname=fullname,
        dob=dob,
        is_admin=is_admin
    )

    try:
        db.session.add(new_user)
        db.session.commit()

        if not is_admin:
            create_default_quiz_for_user(new_user.id)

        return jsonify({"success": True, "message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"success": False, "message": "Registration failed"}), 500


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"success": True, "message": "Logged out"}), 200


def create_default_quiz_for_user(user_id):
    chapters = Chapters.query.all()
    quiz_questions = []

    for chapter in chapters:
        for difficulty in ['easy', 'medium', 'hard']:
            questions = Questions.query.filter_by(chapter_id=chapter.id, difficulty=difficulty).all()
            if len(questions) >= 2:
                quiz_questions.extend(random.sample(questions, 2))

            else:
                print(f"Not enough questions in chapter {chapter.name} for difficulty {difficulty}. Skipping.")
                continue

    default_quiz = Quiz(user_id=user_id, duration='10 mins', remarks='Auto-assigned default quiz')

    db.session.add(default_quiz)
    db.session.commit()

    for question in quiz_questions:
        db.session.add(QuizQuestion(quiz_id=default_quiz.id, question_id=question.id))

    db.session.commit()


#fetch current user in session info
@app.route('/api/user', methods=['GET'])
@login_required
def get_user():
    user = db.session.get(User, current_user.id)
    if user:
        return jsonify({
            'id': user.id,
            'email': user.email,
            'name': user.fullname,
            'dob': user.dob,
            'is_admin': user.is_admin
        })
    return jsonify({"error": "User not found"}), 404
    

#USER
#getting user data
@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard_data():
    user = current_user
    recent_attempts = UserQuiz.query.filter_by(user_id=user.id).order_by(UserQuiz.timestamp.desc()).all()

    streak = 0
    today = datetime.now(timezone.utc).date()
    dates = set([attempt.timestamp.date() for attempt in recent_attempts])
    for i in range(10):
        if (today - timedelta(days=i)) in dates:
            streak += 1
        else:
            break

    total_xp = sum([attempt.score or 0 for attempt in recent_attempts])
    level = "Beginner"
    if total_xp > 100: level = "Intermediate"
    if total_xp > 300: level = "Advanced"

    total_chapters = Chapters.query.count()
    attempted_chapters = (
        db.session.query(Performance.chapter_id)
        .filter_by(user_id=user.id)
        .distinct()
        .count()
    )
    overall_progress = round((attempted_chapters / total_chapters) * 100) if total_chapters else 0
    avg_score = round(total_xp / len(recent_attempts), 2) if recent_attempts else 0

    total_minutes = len(recent_attempts) * 10
    time_spent = f"{total_minutes // 60} hrs {total_minutes % 60} min"

    perf = Performance.query.filter_by(user_id=user.id).all()
    hard = sum(p.hard_correct for p in perf)
    medium = sum(p.medium_correct for p in perf)
    easy = sum(p.easy_correct for p in perf)
    adaptive_level = "Beginner"
    if hard > medium and hard > easy:
        adaptive_level = "Advanced"
    elif medium > easy:
        adaptive_level = "Intermediate"

    subject_stats = []
    chapters = Chapters.query.all()
    for ch in chapters:
        ch_perf = Performance.query.filter_by(user_id=user.id, chapter_id=ch.id).first()
        total_correct = 0
        if ch_perf:
            total_correct = ch_perf.easy_correct + ch_perf.medium_correct + ch_perf.hard_correct
        completion = min(100, total_correct * 10)
        subject_stats.append({
            "name": ch.name,
            "icon": "📘",
            "completion": completion,
            "buttonText": "Continue" if total_correct else "Start Quiz"
        })

    return jsonify({
        "streak": streak,
        "xp": int(total_xp),
        "level": level,
        "overallProgress": overall_progress,
        "avgScore": avg_score,
        "timeSpent": time_spent,
        "adaptiveLevel": adaptive_level,
        "subjectStats": subject_stats,
        "user": {
            "id": user.id,
            "name": user.fullname,
            "email": user.email,
        }
    })


#available quizzes for a particular user
@app.route('/api/user/quizzes', methods=['GET'])
@login_required
def get_available_quizzes():
    quizzes = Quiz.query.filter_by(user_id=current_user.id).all()
    user = db.session.get(User, current_user.id)

    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.fullname,
        },
        "quizzes": [{
            "id": quiz.id,
            "remarks": quiz.remarks,
            "duration": quiz.duration,
        } for quiz in quizzes]
    })


@app.route('/api/quiz/<int:quiz_id>', methods=['GET'])
@login_required
def get_quiz_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)

    if quiz.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    questions = []
    for quiz_question in quiz.questions:
        question = quiz_question.question
        questions.append({
            'id': question.id,
            'question': question.question,
            'option_a': question.option_a,
            'option_b': question.option_b,
            'option_c': question.option_c,
            'option_d': question.option_d,
        })

    return jsonify({'questions': questions})

def get_user_performance_state(user_id):
    # Retrieve all performance records for the user
    performance_data = Performance.query.filter_by(user_id=user_id).all()
    
    # Initialize a performance map for each chapter and difficulty level
    performance_map = {1: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}},
                       2: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}},
                       3: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}},
                       4: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}},
                       5: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}},
                       6: {'easy': {'correct': 0, 'total': 0}, 'medium': {'correct': 0, 'total': 0}, 'hard': {'correct': 0, 'total': 0}}}

    # Populate performance_map with data from the Performance table
    for record in performance_data:
        # Update correct answers and total questions attempted for each difficulty
        performance_map[record.chapter_id]['easy']['correct'] += record.easy_correct
        performance_map[record.chapter_id]['medium']['correct'] += record.medium_correct
        performance_map[record.chapter_id]['hard']['correct'] += record.hard_correct

        performance_map[record.chapter_id]['easy']['total'] += record.easy_total
        performance_map[record.chapter_id]['medium']['total'] += record.medium_total
        performance_map[record.chapter_id]['hard']['total'] += record.hard_total

    # Normalize performance data for each chapter and difficulty
    state = []
    for chapter in performance_map:
        for difficulty in ['easy', 'medium', 'hard']:
            correct = performance_map[chapter][difficulty]['correct']
            total = performance_map[chapter][difficulty]['total']
            # Normalize to a fraction (correct / total), avoiding division by zero
            normalized_score = correct / total if total > 0 else 0.0
            state.append(normalized_score)

    return {'state': state}

@app.route("/api/quiz/<int:quiz_id>/submit", methods=["POST"])
@login_required
def submit_quiz(quiz_id):
    data = request.json
    user_answers = data.get('answers')  # { question_id: selected_option }

    # Record the current quiz attempt
    user_quiz = UserQuiz(user_id=current_user.id, quiz_id=quiz_id)
    db.session.add(user_quiz)
    db.session.commit()

    total_questions = len(user_answers)
    correct_answers = sum(1 for q_id, user_ans in user_answers.items() if Questions.query.get(q_id).correct_answer == user_ans)

    # Calculate the score of the submitted quiz
    score = correct_answers / total_questions if total_questions > 0 else 0.0

    # Store score in UserQuiz table
    user_quiz.score = score
    db.session.commit()

    performance_map = {}
    difficulty_count = {'easy': 0, 'medium': 0, 'hard': 0}

    # Store the user's responses and calculate performance for each chapter/difficulty
    for q_id, user_ans in user_answers.items():
        question = Questions.query.get(q_id)
        if not question:
            continue
        is_correct = question.correct_answer == user_ans

        user_response = UserResponse(
            attempt_id=user_quiz.id,
            question_id=question.id,
            user_answer=user_ans,
            is_correct=is_correct,
            chapter_id=question.chapter_id
        )
        db.session.add(user_response)

        # Update performance map
        ch = question.chapter_id
        diff = question.difficulty
        if ch not in performance_map:
            performance_map[ch] = {'easy': 0, 'medium': 0, 'hard': 0}
        if is_correct:
            performance_map[ch][diff] += 1

        # Count total questions per difficulty level
        difficulty_count[diff] += 1

    db.session.commit()

    # Save the performance data for each chapter/difficulty
    for ch_id, counts in performance_map.items():
        # The total number of questions attempted per difficulty
        easy_total = difficulty_count['easy']
        medium_total = difficulty_count['medium']
        hard_total = difficulty_count['hard']

        perf = Performance(
            user_id=current_user.id,
            chapter_id=ch_id,
            quiz_id=quiz_id,
            easy_correct=counts['easy'],
            medium_correct=counts['medium'],
            hard_correct=counts['hard'],
            easy_total=easy_total,
            medium_total=medium_total,
            hard_total=hard_total
        )
        db.session.add(perf)

    db.session.commit()

    # Integrating Deep Q-Learning logic to generate the next quiz
    try:
        # Retrieve state from user performance
        state = get_user_performance_state(current_user.id)['state']

        # Initialize the agent and environment (ensure agent is correctly initialized elsewhere)
        env = QuizEnv()
        agent = DQNAgent(state_size=18, action_size=18)

        # The agent selects the next quiz configuration (chapter + difficulty)
        action = agent.act(state)
        next_chapter, next_difficulty = env.decode_action(action)

        # Use this to generate a new quiz
        new_questions = generate_adaptive_quiz(performance_map, next_chapter, next_difficulty, num_questions=20)

    except Exception as e:
        print(f"[ERROR] Failed to generate adaptive quiz: {e}")
        return jsonify({'error': 'Quiz submitted but new quiz generation failed.'}), 500

    # Create a new quiz entry in the database for the user
    new_quiz = Quiz(user_id=current_user.id, duration='15 mins', remarks='Auto-generated')
    db.session.add(new_quiz)
    db.session.commit()

    # Add questions to the newly generated quiz
    for q in new_questions:
        qq = QuizQuestion(quiz_id=new_quiz.id, question_id=q.id)
        db.session.add(qq)

    db.session.commit()

    # Include the next quiz selection in the response (for transparency)
    next_quiz_plan = {
        "selected_chapter": next_chapter,
        "difficulty": next_difficulty,
        "reason": f"Low scores in {next_chapter} ({next_difficulty})"
    }

    return jsonify({
        'message': 'Quiz submitted and new quiz generated.',
        'new_quiz_id': new_quiz.id,
        'nextQuizPlan': next_quiz_plan
    }), 200




@app.route('/quiz-history', methods=['GET'])
@login_required
def get_quiz_history():
    user_id = current_user.id
    quizzes = UserQuiz.query.filter_by(user_id=user_id).all()
    quiz_data = []

    for quiz_attempt in quizzes:
        quiz = db.session.get(Quiz, quiz_attempt.quiz_id)
        if not quiz:
            continue

        responses = UserResponse.query \
            .filter_by(attempt_id=quiz_attempt.id) \
            .join(Questions, UserResponse.question_id == Questions.id) \
            .join(Chapters, Questions.chapter_id == Chapters.id) \
            .add_columns(Chapters.name.label('chapter_name'), Questions.difficulty, UserResponse.is_correct) \
            .all()

        breakdown = {}  # { (chapter, difficulty): { correct: X, incorrect: Y } }

        for _, chapter_name, difficulty, is_correct in responses:
            key = (chapter_name, difficulty)
            if key not in breakdown:
                breakdown[key] = {"correct": 0, "incorrect": 0}
            if is_correct:
                breakdown[key]["correct"] += 1
            else:
                breakdown[key]["incorrect"] += 1

        chapter_entries = []
        total_correct = 0
        total_incorrect = 0

        for (chapter, difficulty), stats in breakdown.items():
            chapter_entries.append({
                "chapter": chapter,
                "difficulty": difficulty,
                "correct": stats["correct"],
                "incorrect": stats["incorrect"]
            })
            total_correct += stats["correct"]
            total_incorrect += stats["incorrect"]

        total_questions = total_correct + total_incorrect
        accuracy = round((total_correct / total_questions) * 100, 2) if total_questions > 0 else 0

        quiz_data.append({
            "quiz_id": quiz.id,
            "remarks": quiz.remarks,
            "score": quiz_attempt.score,
            "total": total_questions,
            "accuracy": accuracy,
            "correctAnswers": total_correct,
            "incorrectAnswers": total_incorrect,
            "timeTaken": quiz.duration,
            "timestamp": quiz_attempt.timestamp.isoformat(),
            "chapters": chapter_entries
        })

    return jsonify({
        'user': {
            'id': current_user.id,
            'name': current_user.fullname,
            'email': current_user.email,
        },
        'quizzes': quiz_data
    })


#confirm their usage

@app.route('/quiz/<int:quiz_id>', methods=['GET'])
@login_required
def get_quiz_details(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    questions = QuizQuestion.query.filter_by(quiz_id=quiz_id).all()
    question_data = []

    for quiz_question in questions:
        question = Questions.query.get(quiz_question.question_id)
        user_response = UserResponse.query.filter_by(attempt_id=quiz.id, question_id=question.id).first()
        is_correct = user_response.is_correct if user_response else False

        question_data.append({
            "question": question.question,
            "options": {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d
            },
            "correct_answer": question.correct_answer,
            "user_answer": user_response.user_answer if user_response else None,
            "is_correct": is_correct
        })

    return jsonify({
        "quiz_id": quiz.id,
        "remarks": quiz.remarks,
        "duration": quiz.duration,
        "questions": question_data
    })



@app.route('/performance/<int:user_id>', methods=['GET'])
@login_required
def get_performance(user_id):
    performance_data = Performance.query.filter_by(user_id=user_id).all()
    performance_summary = []

    for performance in performance_data:
        chapter = performance.chapter
        performance_summary.append({
            "chapter": chapter.name,
            "easy_correct": performance.easy_correct,
            "medium_correct": performance.medium_correct,
            "hard_correct": performance.hard_correct
        })

    return jsonify(performance_summary)




#ADMIN
#all routes
@app.route('/api/users/not_admins', methods=['GET'])
def get_non_admin_users():
    users = User.query.filter_by(is_admin=False).all()
    user_data = [{
        'id': user.id,
        'fullname': user.fullname,
        'email': user.email,
        'dob': user.dob
    } for user in users]
    return jsonify({'users': user_data}), 200

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user or user.is_admin:
        return jsonify({'error': 'User not found or is admin'}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted successfully'}), 200

@app.route('/api/user/<int:user_id>/performance', methods=['GET'])
def get_user_performance(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        user_quizzes = UserQuiz.query.filter_by(user_id=user_id).all()
        quizzes_performance = []

        for uq in user_quizzes:
            quiz = uq.quiz  # use relationship instead of extra query

            # Get responses only for this quiz attempt
            responses = UserResponse.query.filter_by(attempt_id=uq.id).all()

            chapter_stats = {}
            total_correct = 0
            total_questions = 0

            for response in responses:
                chapter = response.chapter  # relationship via backref
                if not chapter:
                    continue  # safety check

                chapter_name = chapter.name
                if chapter_name not in chapter_stats:
                    chapter_stats[chapter_name] = {"easy": [0, 0], "medium": [0, 0], "hard": [0, 0]}

                question = response.question_obj
                level = question.difficulty
                correct = 1 if response.user_answer == question.correct_answer else 0

                chapter_stats[chapter_name][level][0] += correct
                chapter_stats[chapter_name][level][1] += 1
                total_correct += correct
                total_questions += 1

            formatted_chapters = []
            for chapter_name, levels in chapter_stats.items():
                formatted_chapters.append({
                    "chapter": chapter_name,
                    "easy": f"{levels['easy'][0]}/{levels['easy'][1]}",
                    "medium": f"{levels['medium'][0]}/{levels['medium'][1]}",
                    "hard": f"{levels['hard'][0]}/{levels['hard'][1]}",
                })

            quizzes_performance.append({
                "quiz_id": quiz.id,
                "remarks": quiz.remarks,
                "duration": quiz.duration,
                "score": (total_correct / total_questions) * 100 if total_questions else 0,
                "chapter_stats": formatted_chapters
            })

        return jsonify({
            "user": {
                "id": user.id,
                "fullname": user.fullname,
                "email": user.email,
            },
            "quizzes": quizzes_performance
        })

    except Exception as e:
        print(f"Error fetching performance data: {e}")
        return jsonify({"error": "Internal server error"}), 500



def performance_to_dict(performance):
    return {
        "id": performance.id,
        "user_id": performance.user_id,
        "chapter_id": performance.chapter_id,
        "easy_correct": performance.easy_correct,
        "medium_correct": performance.medium_correct,
        "hard_correct": performance.hard_correct,
        # Add other fields you need to include
    }

'''@app.route('/api/user/<int:user_id>/performance', methods=['GET'])
def get_user_performance(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        performances = Performance.query.filter_by(user_id=user_id).all()
        if not performances:
            return jsonify({"error": "No performance data found for this user"}), 404

        chapters = Chapters.query.all()
        performance_data = {
            "bestQuiz": None,
            "worstQuiz": None,
            "subjectStats": [],
            "overallScore": 0,
            "recommendation": []
        }

        # Determine best and worst quiz
        best_quiz = max(performances, key=lambda p: p.easy_correct + p.medium_correct + p.hard_correct, default=None)
        worst_quiz = min(performances, key=lambda p: p.easy_correct + p.medium_correct + p.hard_correct, default=None)

        performance_data["bestQuiz"] = performance_to_dict(best_quiz) if best_quiz else None
        performance_data["worstQuiz"] = performance_to_dict(worst_quiz) if worst_quiz else None

        total_correct = 0
        total_questions = 0

        for chapter in chapters:
            # Filter performances for this chapter
            chapter_perfs = [p for p in performances if p.chapter_id == chapter.id]

            if not chapter_perfs:
                continue

            easy_correct = sum(p.easy_correct for p in chapter_perfs)
            medium_correct = sum(p.medium_correct for p in chapter_perfs)
            hard_correct = sum(p.hard_correct for p in chapter_perfs)

            easy_total = sum(p.easy_total for p in chapter_perfs)
            medium_total = sum(p.medium_total for p in chapter_perfs)
            hard_total = sum(p.hard_total for p in chapter_perfs)

            # Calculate score %
            easy_score = (easy_correct / easy_total) * 100 if easy_total else 0
            medium_score = (medium_correct / medium_total) * 100 if medium_total else 0
            hard_score = (hard_correct / hard_total) * 100 if hard_total else 0

            # Determine weakness flag
            flag = "🟢 Strong"
            if easy_score < 70 and medium_score < 60 and hard_score < 50:
                flag = "🔴 All Levels Weak"
            elif hard_score < 50:
                flag = "🔴 Hard"
            elif medium_score < 60:
                flag = "🟡 Medium"
            elif easy_score < 70:
                flag = "🟠 Easy"

            performance_data["subjectStats"].append({
                "chapter": chapter.name,
                "easy": f"{easy_correct}/{easy_total}",
                "medium": f"{medium_correct}/{medium_total}",
                "hard": f"{hard_correct}/{hard_total}",
                "weakness": flag
            })

            # For recommendation section
            if flag.startswith("🔴") or flag.startswith("🟡") or flag.startswith("🟠"):
                performance_data["recommendation"].append(f"{chapter.name} ({flag.split()[-1]})")

            # Update totals
            total_correct += easy_correct + medium_correct + hard_correct
            total_questions += easy_total + medium_total + hard_total

        performance_data["overallScore"] = (total_correct / total_questions) * 100 if total_questions else 0

        return jsonify({
            "user": {
                "id": user.id,
                "fullname": user.fullname,
                "email": user.email,
            },
            "performance": performance_data
        })

    except Exception as e:
        print(f"Error fetching performance data: {e}")
        return jsonify({"error": "Internal server error"}), 500

'''

if __name__ == '__main__':
    with app.app_context():
        app.run(host='0.0.0.0', port=5000, debug=True)
