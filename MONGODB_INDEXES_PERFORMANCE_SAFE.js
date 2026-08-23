// SmartLearningLab - performance indexes
// Safe: each index is isolated so one failure does not stop the script.
use smart_learning_lab;

function safe(collection, keys, options) {
  try {
    db.getCollection(collection).createIndex(keys, options);
    print(`OK   ${collection}.${options.name}`);
  } catch (e) {
    print(`SKIP ${collection}.${options.name} -> ${e}`);
  }
}

safe('users', {role:1, is_active:1}, {name:'ix_users_role_active'});
safe('courses', {is_published:1, featured:-1, created_at:-1}, {name:'ix_courses_publish_feature_created'});
safe('courses', {is_published:1, category:1, created_at:-1}, {name:'ix_courses_publish_category_created'});
safe('courses', {is_published:1, exam:1, created_at:-1}, {name:'ix_courses_publish_exam_created'});
safe('courses', {is_published:1, level:1, created_at:-1}, {name:'ix_courses_publish_level_created'});
safe('topics', {course_id:1, is_published:1, order:1}, {name:'ix_topics_course_publish_order'});
safe('lessons', {course_id:1, is_published:1, order:1}, {name:'ix_lessons_course_publish_order'});
safe('lessons', {course_id:1, topic_id:1, is_published:1, order:1}, {name:'ix_lessons_course_topic_publish_order'});
safe('lesson_resources', {lesson_id:1, order:1}, {name:'ix_lesson_resources_lesson_order'});
safe('course_resources', {course_id:1, order:1}, {name:'ix_course_resources_course_order'});
safe('quizzes', {is_published:1, course_id:1, created_at:-1}, {name:'ix_quizzes_publish_course_created'});
safe('questions', {quiz_id:1}, {name:'ix_questions_quiz'});
safe('enrollments', {user_id:1, status:1, updated_at:-1}, {name:'ix_enrollments_user_status_updated'});
safe('progress', {user_id:1, course_id:1, completed:1, lesson_id:1}, {name:'ix_progress_user_course_completed_lesson'});
safe('progress', {user_id:1, completed:1}, {name:'ix_progress_user_completed'});
safe('test_attempts', {user_id:1, test_id:1, status:1, submitted_at:-1}, {name:'ix_attempts_user_test_status_submitted'});
safe('test_attempts', {user_id:1, status:1, submitted_at:-1}, {name:'ix_attempts_user_status_submitted'});
safe('bookmarks', {user_id:1, item_type:1, item_id:1}, {name:'ix_bookmarks_user_item'});
safe('bookmarks', {user_id:1, created_at:-1}, {name:'ix_bookmarks_user_created'});
safe('course_reviews', {course_id:1, created_at:-1}, {name:'ix_course_reviews_course_created'});
safe('certificates', {user_id:1, issued_at:-1}, {name:'ix_certificates_user_issued'});
safe('notifications', {user_id:1, read:1, created_at:-1}, {name:'ix_notifications_user_read_created'});
safe('notes', {user_id:1, lesson_id:1, updated_at:-1}, {name:'ix_notes_user_lesson_updated'});
safe('activity_events', {user_id:1, created_at:-1}, {name:'ix_activity_user_created'});
safe('video_progress', {user_id:1, lesson_id:1}, {name:'ix_video_progress_user_lesson'});

print('Performance index pass completed. Failed indexes were skipped.');
