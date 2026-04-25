Mobile web app (Expo) static files go here.

Build in cc_mobile_ui:
  npm run export:web

Copy the ENTIRE contents of cc_mobile_ui/dist/ into this directory — including the
"_expo" folder (JavaScript bundles live there). If you only copy index.html, /app
will load a blank page because the browser cannot run the main script.

Example from cc_mobile_ui repo root:
  rsync -a dist/ ../cc_mobile/website/cc_mobile_web/

Adjust paths if your folders differ. To replace an old bundle completely, remove
website/cc_mobile_web/_expo first or use rsync --delete (that can remove files not
present in dist, e.g. this README, so re-copy README.txt if needed).

Public URLs (FastAPI main.py):
  https://<your-host>/app/
  https://<your-host>/app/login
  https://<your-host>/app/register

Set EXPO_PUBLIC_BACKEND_URL when exporting to your public API origin, e.g. https://your-host.com
