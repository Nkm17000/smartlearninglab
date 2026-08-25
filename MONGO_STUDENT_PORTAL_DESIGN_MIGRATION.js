// Smart Learning Lab - Student Home/Course/Quiz taxonomy migration
// Run once in MongoDB Shell. It is designed to be additive/backward-compatible.
// It keeps the legacy `category` field and adds `categories`, `subject` and
// `quiz_group_key` where they are missing.

const EXAM_CATEGORIES = [
  "SSC", "Railway", "Banking", "UPSC", "Computer", "Teaching",
  "Defence", "State Exams", "General", "English Spoken", "Other"
];

const SUBJECTS = [
  "English", "Hindi", "Math", "Reasoning", "General Awareness", "Current Affairs",
  "Science", "Physics", "Chemistry", "Biology", "Computer", "Java", "Python",
  "PHP", "SQL", "DBMS", "Operating Systems", "Networking", "Web Development",
  "Spring Boot", "Microservices", "Aptitude", "Other"
];

function canonical(value, list) {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  if (!text) return null;
  const found = list.find(x => x.toLowerCase() === text.toLowerCase());
  return found || text;
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String).map(x => x.trim()).filter(Boolean);
  if (value === null || value === undefined || String(value).trim() === "") return [];
  return String(value).split(/[,|]/).map(x => x.trim()).filter(Boolean);
}

function unique(values) {
  const out = [];
  const seen = new Set();
  values.forEach(value => {
    const text = String(value).trim();
    const key = text.toLowerCase();
    if (text && !seen.has(key)) {
      seen.add(key);
      out.push(text);
    }
  });
  return out;
}

// ---------------------------------------------------------------------------
// COURSES
// ---------------------------------------------------------------------------
db.courses.find({}).forEach(course => {
  let categories = asArray(course.categories);

  if (!categories.length) {
    const legacyCategory = canonical(course.category, EXAM_CATEGORIES);
    const legacySubject = canonical(course.category, SUBJECTS);
    const exam = canonical(course.exam, EXAM_CATEGORIES);

    if (exam) categories.push(exam);
    else if (legacyCategory) categories.push(legacyCategory);
    else categories.push("General");

    // If old category was actually a subject (e.g. English), preserve it as
    // subject and use General as the exam category.
    if (!course.subject && legacySubject) {
      db.courses.updateOne(
        { _id: course._id },
        { $set: { subject: legacySubject } }
      );
    }
  }

  categories = unique(categories.map(x => canonical(x, EXAM_CATEGORIES) || x));
  const subject = canonical(course.subject, SUBJECTS) || "General";

  db.courses.updateOne(
    { _id: course._id },
    {
      $set: {
        categories: categories.length ? categories : ["General"],
        category: categories[0] || "General",
        subject: subject
      }
    }
  );
});

// ---------------------------------------------------------------------------
// QUIZZES
// ---------------------------------------------------------------------------
db.quizzes.find({}).forEach(quiz => {
  let categories = asArray(quiz.categories);
  let subject = canonical(quiz.subject, SUBJECTS);
  const legacyCategory = String(quiz.category || "").trim();
  const examCategory = canonical(legacyCategory, EXAM_CATEGORIES);
  const subjectCategory = canonical(legacyCategory, SUBJECTS);

  if (!categories.length) {
    if (examCategory) {
      categories = [examCategory];
    } else if (subjectCategory) {
      // Older imports sometimes used category="English" for the subject.
      categories = ["General"];
      if (!subject) subject = subjectCategory;
    } else {
      categories = ["General"];
    }
  }

  categories = unique(categories.map(x => canonical(x, EXAM_CATEGORIES) || x));
  subject = subject || "General";

  const title = String(quiz.title || quiz.name || "").trim();
  const groupKey = `${subject}|${title}`.replace(/\s+/g, " ").trim().toLowerCase();

  db.quizzes.updateOne(
    { _id: quiz._id },
    {
      $set: {
        categories: categories.length ? categories : ["General"],
        category: categories[0] || "General",
        subject,
        quiz_group_key: groupKey
      }
    }
  );
});

// ---------------------------------------------------------------------------
// PERFORMANCE INDEXES
// ---------------------------------------------------------------------------
db.courses.createIndex({ categories: 1 });
db.courses.createIndex({ subject: 1 });
db.courses.createIndex({ is_published: 1, categories: 1, subject: 1 });
db.quizzes.createIndex({ categories: 1 });
db.quizzes.createIndex({ subject: 1 });
db.quizzes.createIndex({ quiz_group_key: 1 });
db.quizzes.createIndex({ is_published: 1, categories: 1, subject: 1 });
db.test_attempts.createIndex({ user_id: 1, status: 1, test_id: 1 });

print("Student portal taxonomy migration completed.");
