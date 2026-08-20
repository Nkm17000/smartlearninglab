# Smart Learning Lab — Final Backend

## MongoDB
No separate `MONGODB_DB` variable is used. Put the database name in `MONGODB_URI`:

MONGODB_URI=mongodb+srv://username:password@smartstudylab.juh84i5.mongodb.net/smart_learning_lab

## Run
pip install -r requirements.txt
python seed_admin.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

Swagger: http://127.0.0.1:8000/docs

## Demo accounts
Admin: admin@smartlearninglab.com / ChangeMe123!
Student: nitin@example.com / Password123!

## Admin content model
Course
  -> Module / Topic
      -> Lesson
          -> progress
  -> Quiz
      -> Question Bank questions

Courses support:
- title/name
- description and short description
- category
- language
- level
- learning objectives
- prerequisites
- estimated duration
- thumbnail URL
- publish/draft

Modules support:
- title/name
- description
- learning objectives
- order
- estimated minutes

Lessons support:
- title/name
- description
- rich text/content
- duration
- resources
- order
- publish/draft

Questions support:
- MCQ options
- correct answer
- difficulty
- marks
- negative marks
- explanation

Quizzes support:
- course/module association
- duration
- passing percentage
- attempts
- question list
- publish/draft
- add existing question
- create new question directly inside quiz

Student supports:
- dashboard
- course discovery
- enrollment
- modules/lessons
- progress
- quizzes
- quiz questions
- attempts/results
- notes
