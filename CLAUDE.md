# Simplify Manual WP Actions - Development Documentation

## Project Overview

A **WHM + cPanel plugin** for bulk updating WordPress plugins and themes across multiple sites via manual zip file upload. Updates only sites where the plugin/theme is already installed (never installs new).

## Current Architecture (v1.0)

**Pure Perl Implementation:**
- **Backend**: Perl CGI scripts with native cPanel/WHM modules
- **Frontend**: Template Toolkit templates (cPanel/WHM master template integration)
- **WordPress Integration**: WP-CLI for plugin/theme detection
- **File Operations**: Archive::Zip for extraction and backup
- **Security**: User-scoped paths, validated against homedir
- **Cleanup**: Cron-based automatic backup expiration (daily)

### Key Components:
1. **WHM Plugin** (`whm/simplify_manual_wp_actions.cgi` + template) - Status & uninstall
2. **cPanel Plugin** (`cpanel/index.cgi` + template) - Main functionality
3. **Cleanup Script** (`cleanup_backups.pl`)
4. **Installation** (`install.sh` + `uninstall.sh`)

## Features

### Core Functionality
- **Bulk update plugins/themes** across multiple WordPress sites
- **Drag & drop zip upload** with validation
- **Plugin vs Theme toggle** for update type selection
- **Smart detection** - Only shows sites where item is installed
- **Optional backups** before updating (14-day retention)
- **Real-time progress** display with per-site status
- **Continue on error** - Failures don't stop remaining updates

### WordPress Integration
- **Site discovery** via filesystem scanning (wp-config.php detection)
- **1-hour caching** of scan results for performance
- **WP-CLI integration** for installed plugin/theme detection
- **Version display** shows current version before update

### Security & Access Control
- **cPanel**: Scoped to logged-in user's sites only
- **Path validation** for all file operations
- **Zip security** - Checks for path traversal attacks
- **Proper ownership** - Files match wp-content owner
- **Input sanitization** for audit logging

### Automation
- **Daily cron job** for backup cleanup (3 AM)
- **14-day retention** for backups
- **24-hour cleanup** for orphaned temp directories
- **Comprehensive logging** (`/var/log/simplify_manual_wp_actions/`)

## User Interface

### Workflow
1. **Select Update Type** - Plugin or Theme (radio buttons)
2. **Upload Zip** - Drag & drop or click to browse (max 50 MB)
3. **Select Sites** - Table shows only sites with item installed
4. **Configure Options** - Enable/disable backup
5. **Start Update** - Progress modal with real-time log
6. **Review Results** - Summary of successes and failures

### Progress Display
- Progress bar with percentage
- Current site being updated
- Scrolling log with timestamps
- Success/failure markers per site
- Final summary with counts

## File Structure

```
simplify_manual_wp_actions/
├── whm/                                     # WHM integration
│   ├── simplify_manual_wp_actions.cgi       # WHM CGI handler (status/uninstall)
│   └── simplify_manual_wp_actions.tmpl      # WHM Template Toolkit template
├── cpanel/                                  # cPanel integration
│   ├── index.cgi                            # Main CGI handler (Perl)
│   ├── index.html.tt                        # Template Toolkit template
│   ├── index.live.pl                        # Entry point redirector
│   ├── install.json                         # DynamicUI registration
│   └── simplify_manual_wp_actions.svg       # Plugin icon
├── packaging/                               # WHM AppConfig files
│   ├── simplify_manual_wp_actions.conf      # WHM AppConfig registration
│   └── simplify_manual_wp_actions_icon.png  # WHM icon (48x48)
├── cleanup_backups.pl                       # Cron cleanup script
├── install.sh                               # Installation script
├── uninstall.sh                             # Uninstallation script
├── ROADMAP.md                               # Project roadmap
├── README.md                                # User documentation
├── LICENSE                                  # MIT License
└── CLAUDE.md                                # This file
```

## Installation

### Quick Install
```bash
cd simplify_manual_wp_actions
chmod +x install.sh
sudo ./install.sh
```

**What it does:**
1. Creates directories (`/var/log/simplify_manual_wp_actions`, `/var/cache/simplify_manual_wp_actions`)
2. Installs cPanel plugin files (dynamicui method)
3. Installs WHM plugin files (AppConfig method)
4. Sets up daily cron job for cleanup
5. Restarts cpsrvd

### Uninstall
```bash
sudo ./uninstall.sh
```

Or use the **Uninstall button** in WHM → Plugins → Simplify Manual WP Actions

## WHM Interface

The WHM plugin provides a minimal admin interface for server administrators.

### Features
- **Installation Status** - Shows if cPanel plugin is installed
- **Cron Job Status** - Shows if backup cleanup is scheduled
- **Backup Info** - Shows count and total size of stored backups
- **Log Files** - Lists active log files
- **Uninstall Button** - Removes all plugin files, backups, logs, and cron job

### WHM API Actions
- **`get_status`** - Returns installation status, backup count, cron status
- **`uninstall`** - Removes all plugin components and restarts cpsrvd

### Access Control
- Requires root access (`Whostmgr::ACLS::hasroot()`)
- Located in WHM → Plugins section

---

## cPanel API Actions

All POST requests with JSON payloads to `index.cgi`:

### Core Actions
- **`health`** - System health check
- **`scan_wordpress`** - Scan for WordPress sites (with force_scan option)
- **`load_cached_wordpress`** - Load cached scan results
- **`detect_installed`** - Check which sites have a plugin/theme installed

### Update Actions
- **`update_site`** - Update a single site (called sequentially)
- **`cleanup_temp`** - Clean up temporary extraction directory

### Backup Management
- **`list_backups`** - List all backups with metadata (size, age, slug)
- **`delete_all_backups`** - Delete all backup files (manual cleanup)

### File Upload (multipart/form-data)
- POST with `zipfile` and `update_type` parameters
- Returns extracted info (slug, name, version, paths)

## Security

### Access Control
- **cPanel**: Auto-scoped to `$ENV{REMOTE_USER}`
- **Path validation**: All site paths validated against user homedirs
- **Temp validation**: Temp paths must be under designated directory

### Zip File Validation
- Maximum size: 50 MB
- Path traversal check (no `..` or absolute paths)
- Valid plugin/theme structure required

### File Operations
- Operations run as CGI user (cPanel user context)
- Ownership matched to wp-content directory
- Backups stored with restricted permissions

### Audit Logging
- **Location**: `/var/log/simplify_manual_wp_actions/`
- **Format**: Timestamp | User | Action | Details | Result | IP
- **Files**: Per-user log files

## WordPress Detection

### Site Discovery
```perl
# Searches these locations:
$homedir/public_html
$homedir/www
$homedir/domains/*/public_html
```

### Plugin/Theme Detection
Uses WP-CLI to list installed items:
```bash
wp plugin list --path="/path/to/site" --format=json
wp theme list --path="/path/to/site" --format=json
```

## Backup System

### Backup Creation
- Created before update if checkbox enabled
- Stored as zip in `/var/cache/simplify_manual_wp_actions/backups/`
- Filename: `{site_hash}_{slug}_{timestamp}.zip`

### Automatic Cleanup
- Cron runs daily at 3 AM
- Deletes backups older than 14 days
- Deletes temp directories older than 24 hours
- Logs cleanup operations

## Development Notes

### Key Perl Modules
```perl
use Cpanel::JSON();           # cPanel's JSON library
use CGI();                    # Multipart form handling
use Archive::Zip;             # Zip extraction and creation
use File::Path qw(make_path remove_tree);
use File::Copy;
use Cwd 'realpath';
use Digest::MD5 qw(md5_hex);
```

### Response Format
```json
// Success
{
    "ok": true,
    "data": { /* action-specific data */ }
}

// Error
{
    "ok": false,
    "error": {
        "code": "error_code",
        "message": "Human readable message"
    }
}
```

### Template Toolkit Integration
```template-toolkit
[% WRAPPER '_assets/master.html.tt'
    app_key = 'simplify_manual_wp_actions'
    page_title = 'Simplify Manual WP Actions'
%]
<!-- Content here -->
[% END %]
```

## Troubleshooting

### Plugin not appearing in WHM
```bash
# Check AppConfig is registered
ls -la /var/cpanel/apps/simplify_manual_wp_actions.conf

# Re-register AppConfig
/usr/local/cpanel/bin/register_appconfig /var/cpanel/apps/simplify_manual_wp_actions.conf

# Restart cPanel
/scripts/restartsrv_cpsrvd --hard
```

### Plugin not appearing in cPanel
```bash
# Re-run installation
sudo ./install.sh

# Check dynamicui config exists
ls -la /usr/local/cpanel/base/frontend/jupiter/dynamicui/dynamicui_simplify_manual_wp_actions.conf

# Restart cPanel
/scripts/restartsrv_cpsrvd --hard
```

### Check logs
```bash
tail -f /var/log/simplify_manual_wp_actions/cpanel_<username>.log
tail -f /var/log/simplify_manual_wp_actions/cleanup.log
```

### Test WP-CLI
```bash
# As the cPanel user
wp plugin list --path=/home/user/public_html --format=json
```

## Future Enhancements

See [ROADMAP.md](ROADMAP.md) for planned features:
- WHM bulk updates across all cPanel accounts
- Update history/audit log tab
- Rollback feature using backups
- Email notifications
- Scheduled updates
- Version comparison before update

---

**Last Updated**: 2025-12-01
**Version**: 1.0
**Author**: Ryon Whyte
