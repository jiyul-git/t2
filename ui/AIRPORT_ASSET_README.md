# Airport lobby day/night approved art
The seven raster WebP image assets are stored **in this PR** at `ui/web/assets/t2-airport/`.
The source of the night image is a crop of the user-approved reference screenshot, preserving the drawing style. The day image is from the matching illustrated day/night reference set. The content overlays, status, tournament list and action buttons remain HTML and use actual server data.

Preview from Termux after stopping previous port 8766 server:
```sh
REPO="$HOME/t2"
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || REPO="$HOME/storage/downloads/t2-integrated"
git -C "$REPO" fetch origin chatgpt/airport-lobby-day-night-20261016
git -C "$REPO" show FETCH_HEAD:ui/tools/preview_airport_termux.sh | sh
```

No asset ZIP or manual image installation required.

Scope: lobby only. Gameplay table HTML/theme CSS, character portraits, poker engine and wallet data are left unchanged. The old simple SVG airport art is deleted. Original approval is limited to the illustrated lobby; no merge or production deployment requested.

*Screenshot fidelity caveat:* Hero imagery consists of crops of composite illustrative screens rather than individually editable characters/terminal/plane layers. Source scene art may include small originally rendered decorative labels. Functional UI text and tournament values are separate DOM elements. A real-device screenshot comparison is still required before production approval.
