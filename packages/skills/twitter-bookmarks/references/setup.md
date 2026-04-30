# Setup Guide

## Prerequisites

- **Node.js 20+**: `node --version` should show v20 or higher
- **Python 3.10+**: `python3 --version` should show 3.10 or higher
- **curl**: available on all macOS and Linux systems
- **Firefox** (recommended on Linux) or **Chrome/Brave/Arc** (macOS): must be logged into x.com

## Installation

### 1. Install fieldtheory-cli

```bash
# If npm global prefix needs user access:
npm config set prefix ~/.npm-global
export PATH="$HOME/.npm-global/bin:$PATH"

# Install
npm install -g fieldtheory

# Verify
ft --version
```

Add the PATH to your shell config if needed:

```bash
# bash
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc

# zsh
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.zshrc
```

### 2. Install helper scripts

```bash
cp scripts/ft-sync scripts/ft-resolve scripts/ft-articles ~/.local/bin/
chmod +x ~/.local/bin/ft-sync ~/.local/bin/ft-resolve ~/.local/bin/ft-articles
```

Ensure `~/.local/bin` is in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # or ~/.bashrc
```

### 3. Initial sync

```bash
ft-sync
```

**macOS:** This will try fieldtheory's native browser detection first (Chrome, Brave, Arc, Firefox). If that fails, it falls back to extracting Firefox cookies manually.

**Linux:** This extracts cookies directly from Firefox's cookie database. Make sure Firefox is your browser and you're logged into x.com.

### 4. Resolve links

```bash
ft-resolve --all
```

This resolves all t.co shortened URLs in your bookmarks to their real destinations and caches the results. Takes ~2 minutes on first run, instant on subsequent runs.

### 5. Verify

```bash
ft status        # Should show bookmark count and data location
ft stats         # Should show top authors and date range
ft-articles      # Should list bookmarks with article links
```

## Browser-Specific Notes

### Firefox (Linux + macOS)

The `ft-sync` script reads cookies from `~/.mozilla/firefox/*/cookies.sqlite` (Linux) or `~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite` (macOS). If you have multiple Firefox profiles, it picks the most recently modified one.

Firefox cookies are not encrypted on either platform, so extraction is reliable.

### Chrome (macOS only via fieldtheory native)

fieldtheory handles Chrome cookie decryption on macOS via the system Keychain. On Linux, Chrome v11 cookies require GNOME Keyring (`secret-tool`), which may not be available. Use Firefox on Linux instead.

### Brave / Arc (macOS only via fieldtheory native)

Same as Chrome -- works on macOS via fieldtheory's native extraction.

## Uninstalling

```bash
npm uninstall -g fieldtheory
rm ~/.local/bin/ft-sync ~/.local/bin/ft-resolve ~/.local/bin/ft-articles
rm -rf ~/.ft-bookmarks  # removes all local bookmark data
```
