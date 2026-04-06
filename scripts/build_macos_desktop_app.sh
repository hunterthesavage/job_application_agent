#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "Virtual environment not found. Run ./install_mac.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

APP_NAME="$(python - <<'PY'
from config import APP_NAME
print(APP_NAME)
PY
)"
APP_VERSION="$(python - <<'PY'
from config import APP_VERSION
print(APP_VERSION)
PY
)"
BUNDLE_ID="com.hunterthesavage.jobapplicationagent"
APP_BUNDLE_PATH="dist/${APP_NAME}.app"
RELEASE_DIR="dist/desktop-wrapper-release"
ZIP_NAME="JobApplicationAgent-macos-desktop-wrapper-${APP_VERSION}.zip"
ZIP_PATH="${RELEASE_DIR}/${ZIP_NAME}"
DMG_NAME="JobApplicationAgent-macos-desktop-wrapper-${APP_VERSION}.dmg"
DMG_PATH="${RELEASE_DIR}/${DMG_NAME}"
DMG_STAGING_DIR="build/dmg-staging"
DMG_VOLUME_NAME="${APP_NAME} ${APP_VERSION}"

if ! python -c "import PyInstaller" >/dev/null 2>&1; then
  echo "==> Installing PyInstaller into the local virtual environment"
  pip install pyinstaller
fi

echo "==> Cleaning previous desktop app build artifacts"
rm -rf build dist

echo "==> Building macOS desktop app bundle"
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "${APP_NAME}" \
  --osx-bundle-identifier "${BUNDLE_ID}" \
  --collect-all streamlit \
  --collect-all openai \
  --collect-all ddgs \
  --collect-all pywebview \
  --add-data "app.py:." \
  --add-data "greenhouse_boards.txt:." \
  --add-data "lever_boards.txt:." \
  --add-data "services:services" \
  --add-data "views:views" \
  --add-data "ui:ui" \
  --add-data "src:src" \
  --add-data "scripts/run_scheduled_jobs.py:scripts" \
  --add-data "config.py:." \
  desktop_app.py

echo "==> Stamping app bundle metadata"
if /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "${APP_BUNDLE_PATH}/Contents/Info.plist" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${APP_VERSION}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
else
  /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string ${APP_VERSION}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
fi

if /usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "${APP_BUNDLE_PATH}/Contents/Info.plist" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${APP_VERSION}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
else
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string ${APP_VERSION}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
fi

if /usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "${APP_BUNDLE_PATH}/Contents/Info.plist" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${BUNDLE_ID}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
else
  /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string ${BUNDLE_ID}" "${APP_BUNDLE_PATH}/Contents/Info.plist"
fi

echo "==> Re-signing app bundle after metadata updates"
codesign --force --deep --sign - "${APP_BUNDLE_PATH}"
codesign --verify --deep --strict "${APP_BUNDLE_PATH}"

if [ ! -f "${APP_BUNDLE_PATH}/Contents/Resources/scripts/run_scheduled_jobs.py" ]; then
  echo "Scheduled runner script was not packaged into the app bundle."
  exit 1
fi

echo "==> Packaging macOS desktop app zip"
mkdir -p "${RELEASE_DIR}"
rm -f "${ZIP_PATH}"
ditto -c -k --sequesterRsrc --keepParent "${APP_BUNDLE_PATH}" "${ZIP_PATH}"

echo "==> Packaging macOS desktop app dmg"
rm -rf "${DMG_STAGING_DIR}"
mkdir -p "${DMG_STAGING_DIR}"
cp -R "${APP_BUNDLE_PATH}" "${DMG_STAGING_DIR}/"
ln -s /Applications "${DMG_STAGING_DIR}/Applications"
rm -f "${DMG_PATH}"
hdiutil create \
  -volname "${DMG_VOLUME_NAME}" \
  -srcfolder "${DMG_STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

echo
echo "Desktop app bundle created at:"
echo "${APP_BUNDLE_PATH}"
echo
echo "Desktop app zip created at:"
echo "${ZIP_PATH}"
echo
echo "Desktop app dmg created at:"
echo "${DMG_PATH}"
