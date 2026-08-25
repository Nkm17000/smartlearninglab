// Smart Learning Lab - production taxonomy index repair
// Run once in mongosh if you need a manual repair before starting the API.
// The API also performs this repair automatically at startup.

for (const name of ['courses', 'quizzes', 'topics']) {
  const collection = db.getCollection(name);
  for (const index of collection.getIndexes()) {
    const keys = Object.keys(index.key || {});
    if (keys.includes('category_ids') && keys.includes('subcategory_ids')) {
      print(`Dropping unsafe parallel-array index: ${name}.${index.name}`);
      collection.dropIndex(index.name);
    }
  }
}

// Safe: only one array field appears in each compound index.
db.courses.createIndex({ is_published: 1, category_ids: 1, subject: 1 });
db.courses.createIndex({ is_published: 1, subcategory_ids: 1, subject: 1 });
db.quizzes.createIndex({ is_published: 1, category_ids: 1, subject: 1 });
db.quizzes.createIndex({ is_published: 1, subcategory_ids: 1, subject: 1 });

db.courses.getIndexes();
db.quizzes.getIndexes();
print('Taxonomy index repair completed.');
