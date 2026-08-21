# FE syntax fix

Fixed StudentHomeScreen.js:

- Invalid: `opacity: pressed?.85`
- Correct: `opacity: pressed ? 0.85 : 1`

This was a JavaScript parser error, not an Expo, React Native, API, or MongoDB error.
