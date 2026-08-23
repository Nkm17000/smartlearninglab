use smart_learning_lab;

function safeIndex(collection, keys, options) {
  try {
    db.getCollection(collection).createIndex(keys, options);
    print("OK  " + collection + " -> " + options.name);
  } catch (e) {
    print("SKIP " + collection + " -> " + options.name);
    print("  " + e);
  }
}

safeIndex("users", {email:1}, {unique:true, name:"ux_users_email"});
safeIndex("users", {role:1, created_at:-1}, {name:"ix_users_role_created"});

safeIndex("courses", {is_published:1, featured:-1, created_at:-1}, {name:"ix_courses_published_featured_created"});
safeIndex("courses", {category:1}, {name:"ix_courses_category"});
safeIndex("courses", {exam:1}, {name:"ix_courses_exam"});
safeIndex("courses", {level:1}, {name:"ix_courses_level"});
safeIndex("courses", {is_published:1, language:1}, {name:"ix_courses_published_language"});
safeIndex("courses", {is_published:1, is_free:1}, {name:"ix_courses_published_free"});

safeIndex("topics", {course_id:1, is_published:1, order:1}, {name:"ix_topics_course_published_order"});
safeIndex("lessons", {course_id:1, is_published:1, order:1}, {name:"ix_lessons_course_published_order"});
safeIndex("lessons", {topic_id:1, is_published:1, order:1}, {name:"ix_lessons_topic_published_order"});
safeIndex("lesson_resources", {lesson_id:1, order:1}, {name:"ix_lesson_resources_lesson_order"});

safeIndex("quizzes", {is_published:1, course_id:1, created_at:-1}, {name:"ix_quizzes_published_course_created"});
safeIndex("quizzes", {is_published:1, featured:-1, created_at:-1}, {name:"ix_quizzes_published_featured_created"});
safeIndex("questions", {quiz_id:1, is_published:1}, {name:"ix_questions_quiz_published"});

safeIndex("enrollments", {user_id:1, status:1, updated_at:-1}, {name:"ix_enrollments_user_status_updated"});
safeIndex("enrollments", {user_id:1, course_id:1}, {name:"ix_enrollments_user_course"});

safeIndex("progress", {user_id:1, updated_at:-1}, {name:"ix_progress_user_updated"});
safeIndex("progress", {user_id:1, course_id:1, completed:1}, {name:"ix_progress_user_course_completed"});
safeIndex("progress", {user_id:1, lesson_id:1}, {name:"ix_progress_user_lesson"});

safeIndex("test_attempts", {user_id:1, status:1, submitted_at:-1}, {name:"ix_test_attempts_user_status_submitted"});
safeIndex("test_attempts", {user_id:1, test_id:1, status:1, submitted_at:-1}, {name:"ix_test_attempts_user_test_status_submitted"});

safeIndex("course_resources", {course_id:1, order:1}, {name:"ix_course_resources_course_order"});
safeIndex("course_reviews", {course_id:1, created_at:-1}, {name:"ix_course_reviews_course_created"});
safeIndex("bookmarks", {user_id:1, item_type:1, item_id:1}, {name:"ix_bookmarks_user_item"});
safeIndex("bookmarks", {user_id:1, created_at:-1}, {name:"ix_bookmarks_user_created"});
safeIndex("notes", {user_id:1, lesson_id:1, created_at:-1}, {name:"ix_notes_user_lesson_created"});

print("\nSafe SmartLearningLab index script finished. Failed indexes were skipped.");
