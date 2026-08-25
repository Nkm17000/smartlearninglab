// SMART LEARNING LAB
// Safe taxonomy migration for courses + quizzes.
// Run in mongosh after selecting the Smart Learning Lab database.
// No documents are deleted.

const CATEGORIES = [
  "SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence",
  "State Exams", "General", "English Spoken", "Computer", "Other"
];

const SUBJECT_DEFAULT_CATEGORIES = {
  English: ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "English Spoken", "Other"],
  Hindi: ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Math: ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Reasoning: ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Aptitude: ["SSC", "Railway", "Banking", "Teaching", "Defence", "State Exams", "General", "Other"],
  "General Awareness": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  "Current Affairs": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Science: ["SSC", "Railway", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Physics: ["SSC", "Railway", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Chemistry: ["SSC", "Railway", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Biology: ["SSC", "Railway", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
  Java: ["Computer"], Python: ["Computer"], PHP: ["Computer"], SQL: ["Computer"],
  DBMS: ["Computer"], Computer: ["Computer"], "Operating Systems": ["Computer"],
  Networking: ["Computer"], "Web Development": ["Computer"], "Spring Boot": ["Computer"],
  Microservices: ["Computer"]
};

function cleanSubject(value) {
  return String(value || "Other").trim() || "Other";
}

function categoriesFor(subject, existing) {
  if (SUBJECT_DEFAULT_CATEGORIES[subject]) return SUBJECT_DEFAULT_CATEGORIES[subject];

  const source = Array.isArray(existing)
    ? existing
    : (existing ? String(existing).split(",") : []);

  const valid = [...new Set(source.map(x => String(x).trim()).filter(x => CATEGORIES.includes(x)))];
  return valid.length ? valid : ["Other"];
}

// ------------------------------------------------------------
// COURSES
// ------------------------------------------------------------

let courseUpdated = 0;

db.courses.find({}).forEach(course => {
  let subject = cleanSubject(course.subject);

  // Old data often stored the subject in category.
  if ((!course.subject || !String(course.subject).trim()) && course.category && !CATEGORIES.includes(String(course.category))) {
    subject = String(course.category).trim();
  }

  const categories = categoriesFor(subject, course.categories || course.category);

  db.courses.updateOne(
    { _id: course._id },
    {
      $set: {
        subject,
        categories,
        // Legacy field retained for older code.
        category: categories[0],
        updated_at: new Date()
      }
    }
  );

  courseUpdated++;
});

// ------------------------------------------------------------
// QUIZZES
// ------------------------------------------------------------

let quizUpdated = 0;

db.quizzes.find({}).forEach(quiz => {
  let subject = cleanSubject(quiz.subject);

  // Old format: category carried the subject, e.g. category="English".
  if ((!quiz.subject || !String(quiz.subject).trim()) && quiz.category && !CATEGORIES.includes(String(quiz.category))) {
    subject = String(quiz.category).trim();
  }

  const categories = categoriesFor(subject, quiz.categories || quiz.category);
  const title = String(quiz.title || quiz.name || "Untitled Quiz").trim();
  const quizGroupKey = `${subject}|${title}`.toLowerCase().replace(/\s+/g, " ").trim();

  db.quizzes.updateOne(
    { _id: quiz._id },
    {
      $set: {
        subject,
        categories,
        category: categories[0],
        quiz_group_key: quizGroupKey,
        updated_at: new Date()
      }
    }
  );

  quizUpdated++;
});

// ------------------------------------------------------------
// INDEXES
// ------------------------------------------------------------

db.courses.createIndex({ subject: 1 });
db.courses.createIndex({ categories: 1 });
db.courses.createIndex({ is_published: 1, subject: 1, categories: 1 });

db.quizzes.createIndex({ subject: 1 });
db.quizzes.createIndex({ categories: 1 });
db.quizzes.createIndex({ quiz_group_key: 1 });
db.quizzes.createIndex({ is_published: 1, subject: 1, categories: 1 });

print("========================================");
print("TAXONOMY MIGRATION COMPLETED");
print("Courses updated: " + courseUpdated);
print("Quizzes updated: " + quizUpdated);
print("========================================");

print("\nEnglish quiz sample:");
printjson(db.quizzes.findOne(
  { subject: "English" },
  { title: 1, subject: 1, categories: 1, category: 1, quiz_group_key: 1 }
));

print("\nJava quiz sample:");
printjson(db.quizzes.findOne(
  { subject: "Java" },
  { title: 1, subject: 1, categories: 1, category: 1, quiz_group_key: 1 }
));
