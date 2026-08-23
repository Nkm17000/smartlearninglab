# Smart Learning Lab — Render Registration Final

Registration flow is unchanged except for production deployment configuration.

## Production flow
1. FE sends `POST /api/v1/auth/register` to `https://smartlearninglab.onrender.com/api/v1`.
2. BE creates/updates the pending student account.
3. BE sends the confirmation email using the existing SMTP implementation.
4. The email link points to the Render backend:
   `https://smartlearninglab.onrender.com/api/v1/auth/verify-email?token=...`
5. BE verifies the token, activates the account, and redirects to:
   `https://smartlearninglab-react.onrender.com/?verified=success`
6. FE shows the registration-success message and the user can sign in.

## Render environment variables
Keep the secret values configured in Render:
- MONGODB_URI
- JWT_SECRET_KEY
- SMTP_HOST
- SMTP_USERNAME
- SMTP_PASSWORD
- SMTP_FROM
- Google/GitHub OAuth secrets

The repository render configuration supplies the production FE/BE URLs and CORS origin.

## Important
Do not change the existing reset-password, login, OAuth, course, quiz, or other application APIs for this registration deployment.


## Registration timeout fix

The React Native/Expo API client now allows 90 seconds for `/auth/*` requests.
This is intentional for Render deployments where the backend can be cold-starting.
The registration email continues to use the same `send_email()` SMTP mechanism
already used by `/auth/forgot-password`.
