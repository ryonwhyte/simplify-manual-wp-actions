# Simplify Manual WP Actions - Implementation Plan & Roadmap

## Project Overview

**Plugin Name:** Simplify Manual WP Actions
**Plugin ID:** `simplify_manual_wp_actions`
**Purpose:** cPanel plugin for bulk updating WordPress plugins/themes across multiple sites via manual zip upload

## Core Features

### 1. WordPress Site Discovery
- Scan all WordPress installations under user's home directory
- Use existing caching pattern (1-hour TTL) for performance
- Display sites in a table with checkboxes for selection

### 2. Plugin/Theme Detection
- Use WP-CLI to get list of installed plugins/themes per site
- Commands: `wp plugin list --format=json` / `wp theme list --format=json`
- Match by slug/folder name to determine which sites have the plugin/theme installed

### 3. Update Type Selection
- Radio buttons: Plugin (default) or Theme
- Determines target directory: `wp-content/plugins/` vs `wp-content/themes/`

### 4. Zip Upload & Extraction
- File upload via HTML form (multipart/form-data)
- Server-side extraction to temp directory
- Validate zip contains valid plugin/theme structure

### 5. Bulk Update Process
- Sequential processing with real-time UI updates
- For each selected site:
  1. Create backup (optional, with cleanup cron)
  2. Delete existing plugin/theme folder
  3. Copy new version from extracted temp directory
  4. Set correct file ownership (cPanel user)
- Continue on error, log failures

### 6. Backup System
- Optional checkbox: "Create backup before updating"
- Backup location: `/var/cache/simplify_manual_wp_actions/backups/`
- Format: `{site_hash}_{plugin_slug}_{timestamp}.zip`
- Cron job for cleanup (delete backups older than 14 days)

### 7. Progress & Results Display
- Progress counter: "Updating site 3 of 15..."
- Per-site status: Success/Failed with details
- Final summary: X succeeded, Y failed

---

## File Structure

```
simplify_manual_wp_actions/
├── cpanel/
│   ├── index.cgi                    # Main CGI backend (Perl)
│   ├── index.html.tt                # Template Toolkit frontend
│   ├── index.live.pl                # Entry point redirector
│   ├── install.json                 # DynamicUI registration
│   └── simplify_manual_wp_actions.svg  # Plugin icon
├── packaging/
│   └── simplify_manual_wp_actions.conf  # (Future WHM AppConfig)
├── cleanup_backups.pl               # Cron script for backup cleanup
├── install.sh                       # Installation script
├── uninstall.sh                     # Uninstallation script
├── ROADMAP.md                       # This file
├── README.md                        # User documentation
└── CLAUDE.md                        # Development documentation
```

---

## Implementation Phases

### Phase 1: Project Setup & Base Structure - COMPLETED
- [x] Copy existing plugin files as base
- [x] Rename all references from `wp_temp_accounts` to `simplify_manual_wp_actions`
- [x] Update install.json with new plugin metadata
- [x] Update install.sh and uninstall.sh
- [x] Create new SVG icon
- [ ] Verify basic installation works in cPanel

### Phase 2: Backend - Core API Actions - COMPLETED
- [x] Remove unused actions (create_temp_user, delete_temp_user, etc.)
- [x] Keep: `health`, `scan_wordpress`, `load_cached_wordpress`
- [x] Add: `detect_installed` - Get installed plugins/themes for selected sites
- [x] Add: `upload_zip` - Handle zip file upload and extraction (via multipart handling)
- [x] Add: `update_site` - Update a single site
- [x] Add: `cleanup_temp` - Clean up temp extraction directory

### Phase 3: Backend - Update Logic - COMPLETED
- [x] Implement zip extraction to temp directory
- [x] Implement plugin/theme structure validation
- [x] Implement backup creation (zip existing folder)
- [x] Implement folder replacement with proper ownership
- [x] Implement error handling and logging
- [ ] Test update process on single site

### Phase 4: Frontend - UI Components - COMPLETED
- [x] Step 1: Update type selection (Plugin vs Theme radio buttons)
- [x] Step 2: Zip upload with drag & drop
- [x] Step 3: WordPress site table with checkboxes
- [x] Step 4: Backup option and Start Update button
- [x] Select all / Select none buttons

### Phase 5: Frontend - Progress Display - COMPLETED
- [x] Progress modal showing:
  - [x] Current site being updated
  - [x] Progress bar (X of Y)
  - [x] Live status log (scrolling)
  - [x] Per-site result (success/fail)
- [x] Final summary display
- [x] Close/Done button

### Phase 6: Backup Cleanup System - COMPLETED
- [x] Create `cleanup_backups.pl` script
- [x] Add cron job during installation (daily at 3 AM)
- [x] Delete backups older than 14 days
- [x] Delete temp directories older than 24 hours
- [x] Log cleanup operations

### Phase 7: Testing & Polish - PENDING
- [ ] Test with multiple WordPress sites
- [ ] Test with various plugin/theme zips
- [ ] Test error scenarios (permissions, disk space, etc.)
- [ ] Test backup and restore
- [ ] UI polish and error messages
- [ ] Update documentation (README.md, CLAUDE.md)

---

## API Endpoints

### `health`
- **Purpose:** System health check
- **Response:** `{ status: 'ok', user: 'cpanel_user' }`

### `scan_wordpress`
- **Purpose:** Scan for WordPress installations
- **Payload:** `{ force_scan: boolean }`
- **Response:** `[{ path, domain, wp_config }]`

### `load_cached_wordpress`
- **Purpose:** Load cached WordPress scan results
- **Response:** `[{ path, domain, wp_config }]` or `null`

### `detect_installed`
- **Purpose:** Get installed plugins/themes for selected sites
- **Payload:** `{ sites: [{path, domain}], type: 'plugin'|'theme', slug: 'plugin-slug' }`
- **Response:** `{ sites: [{ path, domain, is_installed: boolean, current_version }] }`

### `upload_zip` (multipart form)
- **Purpose:** Upload and extract zip file
- **Payload:** Multipart form data with `zipfile` and `update_type`
- **Response:** `{ temp_id, temp_path, item_path, slug, type, name, version }`

### `update_site`
- **Purpose:** Update a single site (called sequentially from frontend)
- **Payload:** `{ site_path, temp_path, item_path, slug, type, create_backup: boolean }`
- **Response:** `{ success: boolean, backup_path?, message }`

### `cleanup_temp`
- **Purpose:** Clean up temporary extraction directory
- **Payload:** `{ temp_path }`
- **Response:** `{ success: boolean }`

---

## Technical Decisions

### Detection Method: WP-CLI
- More accurate than folder matching
- Provides version info for display
- Commands run in clean environment via `env -i`

### Error Handling: Continue on Failure
- Log failures per site
- Continue with remaining sites
- Show comprehensive summary at end

### Backups: Optional with Auto-Cleanup
- User checkbox to enable/disable (default: enabled)
- Stored in `/var/cache/simplify_manual_wp_actions/backups/`
- Cron cleans up after 14 days
- Named: `{md5(site_path)[0:8]}_{slug}_{timestamp}.zip`

### Upload Limits
- Maximum zip file size: 50 MB
- Validated server-side before extraction

### Progress: Sequential with UI Updates
- Process one site at a time
- Frontend makes sequential API calls
- UI updates after each site completion
- User sees real-time progress

---

## Security Considerations

- [x] Validate zip file before extraction (check for path traversal in filenames)
- [x] Validate site paths against user's home directory
- [x] Validate temp paths against designated temp directory
- [x] Set correct file ownership after copy (match wp-content owner)
- [x] Sanitize all log inputs
- [x] Limit zip file size (50 MB)
- [x] Clean up temp files after operation
- [x] Use Archive::Zip for safe extraction

---

## Future Enhancements (Post-MVP)

- [ ] WHM integration for server-wide updates
- [ ] Update history/audit log tab
- [ ] Rollback feature using backups
- [ ] Email notifications on completion
- [ ] Scheduled updates
- [ ] Plugin/theme version comparison before update
- [ ] Multi-file batch upload
- [ ] Pre-update version display in site table
