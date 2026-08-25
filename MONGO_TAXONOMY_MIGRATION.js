// Smart Learning Lab - exam category + subject taxonomy migration
// Run in mongosh against the SmartLearningLab database.
// Safe to re-run: existing canonical arrays are preserved and normalized.

const EXAM_CATEGORIES = ['SSC','Railway','Banking','UPSC','Computer','Teaching','Defence','State Exams','General','English Spoken','Other'];

function asArray(value, fallback='General') {
  if (Array.isArray(value)) return value.map(String).map(x => x.trim()).filter(Boolean);
  if (value === null || value === undefined || String(value).trim() === '') return [fallback];
  return String(value).split(/[,|]/).map(x => x.trim()).filter(Boolean);
}

function uniq(values) {
  const seen = new Set();
  return values.filter(x => { const k=x.toLowerCase(); if(seen.has(k)) return false; seen.add(k); return true; });
}

function normalizeTitle(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

// 1. Courses: category -> categories[], add subject.
db.courses.find({}).forEach(c => {
  const categories = uniq(asArray(c.categories || c.category));
  const subject = String(c.subject || 'General').trim() || 'General';
  db.courses.updateOne(
    { _id: c._id },
    { $set: {
      categories,
      category: categories[0] || 'General',
      subject,
      taxonomy_version: 2
    }}
  );
});

// 2. Quizzes: category -> categories[], add subject + cross-exam identity.
db.quizzes.find({}).forEach(q => {
  const categories = uniq(asArray(q.categories || q.category));
  const subject = String(q.subject || 'General').trim() || 'General';
  const title = normalizeTitle(q.title || q.name);
  const quiz_group_key = `${subject.toLowerCase()}|${title}`;
  db.quizzes.updateOne(
    { _id: q._id },
    { $set: {
      categories,
      category: categories[0] || 'General',
      subject,
      quiz_group_key,
      taxonomy_version: 2
    }}
  );
});

// 3. Recommended indexes. These are non-destructive.
db.courses.createIndex({ categories: 1 });
db.courses.createIndex({ subject: 1 });
db.courses.createIndex({ is_published: 1, categories: 1, subject: 1 });

db.quizzes.createIndex({ categories: 1 });
db.quizzes.createIndex({ subject: 1 });
db.quizzes.createIndex({ quiz_group_key: 1 });
db.quizzes.createIndex({ is_published: 1, categories: 1, subject: 1 });

db.test_attempts.createIndex({ user_id: 1, status: 1, test_id: 1 });

print('Taxonomy migration complete.');
print('Courses:', db.courses.countDocuments({ taxonomy_version: 2 }));
print('Quizzes:', db.quizzes.countDocuments({ taxonomy_version: 2 }));
