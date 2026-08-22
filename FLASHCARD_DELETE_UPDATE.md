# Flashcard delete update

DELETE `/api/v1/flashcards/{card_id}` deletes only the authenticated student's own flashcard. The frontend displays at most three cards per row/page, with previous/next arrows and a small × delete button.
