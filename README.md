# Simplify Manual WP Actions

A WHM/cPanel plugin for bulk updating WordPress plugins and themes across multiple sites via manual zip file upload.

## Features

- **Bulk Updates**: Update a plugin or theme across all your WordPress sites at once
- **Smart Detection**: Only updates sites where the plugin/theme is already installed (never installs new)
- **Plugin & Theme Support**: Toggle between updating plugins or themes
- **Drag & Drop Upload**: Easy zip file upload with drag & drop support
- **Optional Backups**: Create backups before updating (14-day automatic retention)
- **Real-time Progress**: Watch updates happen in real-time with a detailed log
- **Error Resilience**: Failures on one site don't stop updates on others

## Requirements

- cPanel/WHM server
- WP-CLI installed and accessible
- WordPress sites under standard cPanel paths

## Installation

```bash
# Clone or download the plugin
cd /path/to/simplify_manual_wp_actions

# Make installer executable
chmod +x install.sh

# Run installer as root
sudo ./install.sh
```

After installation, access the plugin:
- **WHM**: Plugins > Simplify Manual WP Actions (status & uninstall)
- **cPanel**: Domains > Simplify Manual WP Actions (main functionality)

## Usage

### Step 1: Select Update Type
Choose whether you're updating a **Plugin** or a **Theme**.

### Step 2: Upload Zip File
Drag and drop your plugin/theme zip file, or click to browse. Maximum file size is 50 MB.

### Step 3: Select Sites
The plugin scans your WordPress installations and shows only sites where the plugin/theme is currently installed. Select which sites to update using the checkboxes.

### Step 4: Start Update
Optionally enable "Create backup before updating" (recommended), then click **Start Bulk Update**.

### Step 5: Monitor Progress
A progress modal shows:
- Current site being updated
- Progress bar
- Live log with timestamps
- Success/failure status for each site
- Final summary

## How It Works

1. **Upload**: Your zip file is uploaded and extracted to a temporary location
2. **Detection**: WP-CLI checks which sites have the plugin/theme installed
3. **Backup** (optional): Existing plugin/theme is zipped before replacement
4. **Update**: Old version is removed and new version is copied in
5. **Ownership**: File ownership is set to match the site's wp-content directory
6. **Cleanup**: Temporary files are automatically removed

## Backup System

When enabled, backups are:
- Stored in `/var/cache/simplify_manual_wp_actions/backups/`
- Named `{site_hash}_{plugin_slug}_{timestamp}.zip`
- Automatically deleted after 14 days
- Can be manually restored if needed

## Logs

Plugin activity is logged to:
- `/var/log/simplify_manual_wp_actions/cpanel_<username>.log` - Per-user activity
- `/var/log/simplify_manual_wp_actions/cleanup.log` - Backup cleanup operations

## Uninstallation

**Option 1: WHM Interface**
Go to WHM → Plugins → Simplify Manual WP Actions and click the **Uninstall** button.

**Option 2: Command Line**
```bash
sudo ./uninstall.sh
```

This removes:
- All plugin files from WHM and cPanel
- Log and cache directories
- Backup files
- Cleanup cron job

## Security

- All operations are scoped to the logged-in cPanel user
- File paths are validated against the user's home directory
- Zip files are checked for path traversal attacks
- File operations maintain proper ownership

## Troubleshooting

### Plugin not appearing in cPanel
```bash
# Re-run installation
sudo ./install.sh

# Or manually restart cPanel
sudo /scripts/restartsrv_cpsrvd --hard
```

### "No WordPress sites found"
Ensure your WordPress installations are in standard locations:
- `~/public_html/`
- `~/domains/*/public_html/`

### Updates failing
Check the logs:
```bash
tail -f /var/log/simplify_manual_wp_actions/cpanel_<username>.log
```

Common issues:
- WP-CLI not installed or not in PATH
- Insufficient permissions
- Disk space issues

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please open an issue on GitHub.
