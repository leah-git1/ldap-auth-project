

# The Front Desk

A Flask + OpenLDAP demo that shows how LDAP authentication works in practice and how a JWT is used to authorize access to protected routes.

This project presents a small identity flow:
- create an LDAP account
- sign in with a real LDAP bind
- receive a JWT with group membership claims
- call protected endpoints for profile/admin checks
- inspect the live directory tree

## Demo video

Watch the project walkthrough:

<video controls width="100%" src="./media/demo/LDAP_demo.mp4">
  Your browser cannot play this video. <a href="./media/demo/LDAP_demo.mp4">Open the demo video</a>.
</video>

If the video player is not supported by your README viewer, [open the demo video](./media/demo/LDAP_demo.mp4).

## Features

- OpenLDAP directory with organizational units and groups
- User registration that writes an `inetOrgPerson` entry
- Login by validating credentials with an LDAP bind
- JWT generation for a signed user session
- Admin-only access checks based on LDAP group membership
- Live directory browsing from the browser
- Interactive trace panel showing the auth flow step by step

## Tech stack

- Python 3
- Flask
- ldap3
- OpenLDAP via Docker
- PyJWT

## Project structure

- `app.py` — Flask API and JWT logic
- `static/index.html` — browser-based demo UI
- `ldif/users.ldif` — seed LDAP directory data
- `docker-compose.yml` — OpenLDAP container setup
- `requirements.txt` — Python dependencies
- `media/demo/` — place your recorded demo video here

## Local setup

1. Start the LDAP container:

   ```bash
   docker compose up -d
   ```

2. Install Python dependencies:

   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python app.py
   ```

4. Open the app in a browser:

   ```text
   http://localhost:5000
   ```

## Demo credentials

The seeded directory includes:

- `dcohen` / `pass1234` — admin user
- `ylevi` / `pass5678` — regular user

## Authentication flow

1. The user signs in with a username and password.
2. The server attempts an LDAP bind against the user DN.
3. If valid, the server searches the group membership for that user.
4. A JWT is issued with the username and group list.
5. Protected routes check the JWT and require the `admins` group for admin access.

## Admin endpoints

The app exposes a few protected routes:

- `/profile` — requires a valid JWT
- `/admin` — requires a valid JWT and `admins` in the group list
- `/api/directory` — admin-only directory listing

## Notes

This project is intended as a learning/demo application for understanding:
- how LDAP binds authenticate users
- how directory metadata can drive authorization
- how JWT claims carry trusted identity context
- how a simple frontend can visualize an auth flow

## License

This project is intended for educational/demo use.
