// Smart Learning Lab - Category/Subcategory normalization
// Run once in mongosh against the Smart Learning Lab database.
// Existing documents are updated in place; nothing is deleted.

const DEFAULT = {
  SSC: ['SSC CGL','SSC CHSL','SSC CPO','SSC MTS','SSC GD'],
  Railway: ['RRB NTPC','RRB Group D','RRB ALP','RRB JE'],
  Banking: ['IBPS PO','IBPS Clerk','SBI PO','SBI Clerk','RBI Grade B','RBI Assistant'],
  UPSC: ['UPSC Civil Services','UPSC CDS','UPSC NDA'],
  Teaching: ['CTET','TET','KVS','DSSSB','REET'],
  Defence: ['NDA','CDS','AFCAT','Agniveer'],
  'State Exams': ['State PSC','State SSC','State Police','State Teacher Exams'],
  General: ['General Competitive Exams','General Knowledge'],
  'English Spoken': ['Spoken English','Business English','Interview English'],
  Computer: ['Computer Fundamentals','Programming','Web Development','Database','Software Development'],
  Other: ['Other Exams','Other Learning']
};

const SUBJECT_CATEGORIES = {
  English: ['SSC','Railway','Banking','UPSC','Teaching','Defence','State Exams','General','English Spoken','Other'],
  Hindi: ['SSC','Railway','Banking','UPSC','Teaching','Defence','State Exams','General','Other'],
  Math: ['SSC','Railway','Banking','UPSC','Teaching','Defence','State Exams','General','Other'],
  Reasoning: ['SSC','Railway','Banking','UPSC','Teaching','Defence','State Exams','General','Other'],
  Java: ['Computer'], Python: ['Computer'], PHP: ['Computer'], SQL: ['Computer'],
  DBMS: ['Computer'], Computer: ['Computer'], 'Operating Systems': ['Computer'],
  Networking: ['Computer'], 'Web Development': ['Computer'], 'Spring Boot': ['Computer'], Microservices: ['Computer']
};

function slug(v){ return String(v).trim().toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''); }
function uniq(a){ return [...new Set((a||[]).filter(Boolean).map(String))]; }
function arr(v){ if(Array.isArray(v)) return uniq(v); if(v==null||v==='') return []; return uniq(String(v).split(',').map(x=>x.trim())); }
function idForCategory(name){ return slug(name); }
function subId(categoryId,name){ return `${categoryId}:${slug(name)}`; }

// 1) Seed taxonomy collections.
for (const [category, subs] of Object.entries(DEFAULT)) {
  const cid = idForCategory(category);
  db.categories.updateOne(
    {_id: cid},
    {$setOnInsert:{_id:cid,name:category,slug:slug(category),is_active:true,created_at:new Date()},$set:{updated_at:new Date()}},
    {upsert:true}
  );
  for (const name of subs) {
    const sid = subId(cid,name);
    db.subcategories.updateOne(
      {_id:sid},
      {$setOnInsert:{_id:sid,category_id:cid,name,slug:slug(name),is_active:true,created_at:new Date()},$set:{updated_at:new Date()}},
      {upsert:true}
    );
  }
}

function subjectDefaultLinks(subject){
  const names = SUBJECT_CATEGORIES[subject] || ['Other'];
  const categoryIds = names.map(idForCategory);
  const subDocs = db.subcategories.find({category_id:{$in:categoryIds},is_active:{$ne:false}}).toArray();
  return {
    category_ids: categoryIds,
    categories: names,
    subcategory_ids: subDocs.map(x=>String(x._id)),
    subcategories: subDocs.map(x=>x.name)
  };
}

function resolveLinks(doc){
  let subject = String(doc.subject || '').trim();
  const legacyCategory = doc.category;
  if(!subject && typeof legacyCategory === 'string' && !DEFAULT[legacyCategory]) subject = legacyCategory.trim();
  if(!subject) subject = 'Other';

  let categories = arr(doc.categories);
  let categoryIds = arr(doc.category_ids);
  let subcategories = arr(doc.subcategories || doc.subcategory);
  let subcategoryIds = arr(doc.subcategory_ids);

  // Old data often stored category:"English". Convert that to the new taxonomy.
  if(!categories.length && !categoryIds.length && typeof legacyCategory === 'string' && legacyCategory.toLowerCase() === subject.toLowerCase()) {
    return {subject, ...subjectDefaultLinks(subject)};
  }

  if(!categoryIds.length) categoryIds = categories.map(x=>idForCategory(x));
  if(!categories.length) categories = categoryIds.map(id=>db.categories.findOne({_id:id})?.name).filter(Boolean);

  // If an old record has no subcategory, leave it unlinked rather than inventing a specific exam.
  if(!subcategoryIds.length && subcategories.length) {
    subcategoryIds = subcategories.map(name=>{
      const found = db.subcategories.findOne({name,category_id:{$in:categoryIds}});
      return found ? String(found._id) : null;
    }).filter(Boolean);
  }
  if(!subcategories.length && subcategoryIds.length) {
    subcategories = subcategoryIds.map(id=>db.subcategories.findOne({_id:id})?.name).filter(Boolean);
  }
  return {subject,category_ids:uniq(categoryIds),categories:uniq(categories),subcategory_ids:uniq(subcategoryIds),subcategories:uniq(subcategories)};
}

// 2) Update courses.
let courseUpdated = 0;
db.courses.find({}).forEach(doc=>{
  const links = resolveLinks(doc);
  db.courses.updateOne({_id:doc._id},{$set:{...links,category:links.categories[0]||'Other',subcategory:links.subcategories[0]||'',updated_at:new Date()}});
  courseUpdated++;
});

// 3) Update quizzes.
let quizUpdated = 0;
db.quizzes.find({}).forEach(doc=>{
  const links = resolveLinks(doc);
  const title = String(doc.title || doc.name || '').trim();
  db.quizzes.updateOne({_id:doc._id},{$set:{...links,category:links.categories[0]||'Other',subcategory:links.subcategories[0]||'',quiz_group_key:`${links.subject}|${title}`.toLowerCase().trim(),updated_at:new Date()}});
  quizUpdated++;
});

// 4) Indexes.
// Remove the old invalid compound multikey indexes if this migration was
// already executed before the parallel-array fix.
for (const collection of [db.courses, db.quizzes]) {
  for (const idx of collection.getIndexes()) {
    const keys = Object.keys(idx.key || {});
    if (keys.includes("category_ids") && keys.includes("subcategory_ids")) {
      collection.dropIndex(idx.name);
    }
  }
}
db.categories.createIndex({slug:1},{unique:true});
db.subcategories.createIndex({category_id:1,slug:1},{unique:true});
db.subcategories.createIndex({category_id:1});
db.courses.createIndex({category_ids:1});
db.courses.createIndex({subcategory_ids:1});
db.courses.createIndex({subject:1});
// IMPORTANT: category_ids and subcategory_ids are both arrays. MongoDB
// cannot index both array fields in the same compound index (parallel
// multikey arrays). Keep each taxonomy array in its own index.
db.courses.createIndex({is_published:1,category_ids:1,subject:1});
db.courses.createIndex({is_published:1,subcategory_ids:1,subject:1});
db.quizzes.createIndex({category_ids:1});
db.quizzes.createIndex({subcategory_ids:1});
db.quizzes.createIndex({subject:1});
db.quizzes.createIndex({quiz_group_key:1});
db.quizzes.createIndex({is_published:1,category_ids:1,subject:1});
db.quizzes.createIndex({is_published:1,subcategory_ids:1,subject:1});

print(`Migration complete. Courses updated: ${courseUpdated}; quizzes updated: ${quizUpdated}`);
print('IMPORTANT: records without a reliable legacy subcategory keep subcategory_ids/subcategories empty; assign their correct subcategory in Admin → Courses/Test Series.');
