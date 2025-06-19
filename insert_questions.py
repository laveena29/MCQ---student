from app import app  # Ensure your app instance is correctly imported
from extensions import db
import pandas as pd
from models import Chapters, Questions

def seed_chapters():
    chapters_data = [
        ("Statistics", "Statistics deals with collecting, analyzing, interpreting, and presenting data to support decision making and understanding patterns."),
        ("Introduction to Trigonometry", "Trigonometry is the branch of mathematics that studies relationships between side lengths and angles of triangles."),
        ("Applications of Trigonometry", "Applications of Trigonometry help in calculating heights and distances in real-life problems involving angles of elevation and depression."),
        ("Probability", "Probability is the study of the likelihood of the occurrence of an event, expressed as a number between 0 and 1."),
        ("Quadratic Equations", "Quadratic Equations are equations in the form ax² + bx + c = 0, where a, b, and c are constants and a ≠ 0."),
        ("Real Numbers", "Real Numbers are all the numbers that can be found on the number line including both rational and irrational numbers.")
    ]

    for name, description in chapters_data:
        existing = Chapters.query.filter_by(name=name).first()
        if not existing:
            db.session.add(Chapters(name=name, description=description))
    db.session.commit()
    print("Chapters seeded.")

def import_questions_from_excel(file_path):
    df = pd.read_excel(file_path)

    for _, row in df.iterrows():
        chapter_name = row['Chapter'].strip()  # Strip spaces for consistency
        chapter = Chapters.query.filter_by(name=chapter_name).first()
        if not chapter:
            print(f"Chapter not found: {chapter_name}")
            continue

        question = Questions(
            chapter_id=chapter.id,
            question=row['Question'],
            difficulty=row['Difficulty'].lower(),
            option_a=row['Option_A'],
            option_b=row['Option_B'],
            option_c=row['Option_C'],
            option_d=row['Option_D'],
            correct_answer=row['Answer']
        )
        db.session.add(question)

    db.session.commit()
    print("Questions imported successfully.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("All tables created successfully.")
        seed_chapters()
        import_questions_from_excel('Final.xlsx')
