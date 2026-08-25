// Run once in mongosh if you want to repair the production database manually.
// The application also performs this repair automatically at startup.

for (const collection of [db.courses, db.quizzes]) {
  for (const idx of collection.getIndexes()) {
    const keys = Object.keys(idx.key || {});
    if (keys.includes('category_ids') && keys.includes('subcategory_ids')) {
      print(`Dropping unsafe index ${collection.getName()}.${idx.name}`);
      collection.dropIndex(idx.name);
    }
  }
}

for (const collection of [db.courses, db.quizzes]) {
  collection.createIndex({category_ids: 1});
  collection.createIndex({subcategory_ids: 1});
  collection.createIndex({subject: 1});
  collection.createIndex({is_published: 1, category_ids: 1, subject: 1});
  collection.createIndex({is_published: 1, subcategory_ids: 1, subject: 1});
}

print('Taxonomy index repair complete.');
