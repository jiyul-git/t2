# Approved airport art asset installation
This draft PR requires real raster artwork. **The CSS vector airport files are no longer used.**
The image zip `t2_airport_final_assets.zip` is supplied separately alongside this draft for Termux preview because the GitHub connector accepts text source but not local binary image uploads. Do not merge or deploy this PR without first adding all seven WebP files under `ui/web/assets/t2-airport/`.

Only lobby files changed. `index.html`, `theme.css`, `visuals.js`, original player portrait PNG files and game modules are untouched.

To preview on an already-running Termux installation:
1. Download the asset ZIP into Android Downloads from the conversation.
2. Fetch this PR into the isolated preview's `web/` folder.
3. Extract `t2-airport/` from the asset ZIP into `$HOME/t2_airport_preview/web/assets/`.
4. Restart the server on port 8766 and hard-refresh the browser.

Design reference: the screenshot supplied in the conversation on 2026-10-16.
