# Simplify Manual WP Actions

A WHM/cPanel plugin for bulk updating WordPress plugins and themes across multiple sites via manual zip file upload.

**Version**: 1.0.2

## Features

### cPanel Interface
- **Bulk Updates**: Update a plugin or theme across all your WordPress sites at once
- **Smart Detection**: Only updates sites where the plugin/theme is already installed (never installs new)
- **Plugin & Theme Support**: Toggle between updating plugins or themes
- **Drag & Drop Upload**: Easy zip file upload with drag & drop support
- **Optional Backups**: Create backups before updating (14-day automatic retention)
- **Real-time Progress**: Watch updates happen in real-time with a detailed log
- **Error Resilience**: Failures on one site don't stop updates on others

### Backup Management
- **View Backups**: See all stored backups with metadata (type, website, date)
- **Filter by Type**: Filter backups by plugins or themes
- **Restore Backups**: One-click restore to original location
- **Delete Backups**: Remove individual backups when no longer needed

### WHM Interface
- **Status Dashboard**: View installation status, version, backup count, and log info
- **Auto-Update**: Update the plugin directly from GitHub with one click
- **Uninstall**: Clean removal of all plugin components

## Requirements

- cPanel/WHM server
- WP-CLI installed and accessible
- WordPress sites under standard cPanel paths
- Git (for auto-update feature)

## Installation

```bash
# Clone or download the plugin
git clone https://github.com/ryonwhyte/simplify-manual-wp-actions.git
cd simplify-manual-wp-actions

# Make installer executable
chmod +x install.sh

# Run installer as root
sudo ./install.sh
```

After installation, access the plugin:
- **WHM**: Plugins > Simplify Manual WP Actions (status, update & uninstall)
- **cPanel**: Domains > Simplify Manual WP Actions (main functionality)

## Usage

### Updating Plugins/Themes

#### Step 1: Select Update Type
Choose whether you're updating a **Plugin** or a **Theme**.

#### Step 2: Upload Zip File
Drag and drop your plugin/theme zip file, or click to browse. Maximum file size is 50 MB.

#### Step 3: Select Sites
The plugin scans your WordPress installations and shows only sites where the plugin/theme is currently installed. Select which sites to update using the checkboxes.

#### Step 4: Start Update
Optionally enable "Create backup before updating" (recommended), then click **Start Bulk Update**.

#### Step 5: Monitor Progress
A progress modal shows:
- Current site being updated
- Progress bar
- Live log with timestamps
- Success/failure status for each site
- Final summary

### Managing Backups

Navigate to the **Backup Management** section in cPanel to:
- View all backups with website and type information
- Filter by All / Plugins / Themes
- Restore a backup to its original location
- Delete backups you no longer need

### Updating the Plugin

From WHM > Plugins > Simplify Manual WP Actions:
1. Click **Update to Latest Version**
2. Confirm the update
3. The plugin pulls the latest code from GitHub and reinstalls
4. Your backups and logs are preserved

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
- Include metadata (website, type, date, original path)
- Automatically deleted after 14 days via cron job
- Restorable with one click from the Backup Management section

## Logs

Plugin activity is logged to:
- `/var/log/simplify_manual_wp_actions/cpanel_<username>.log` - Per-user activity
- `/var/log/simplify_manual_wp_actions/cleanup.log` - Backup cleanup operations

## Uninstallation

**Option 1: WHM Interface**
Go to WHM > Plugins > Simplify Manual WP Actions and click the **Uninstall** button.

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
- WHM features require root access

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

### Auto-update not working
Ensure Git is installed on the server:
```bash
which git
# If not installed:
yum install git -y
```

## Changelog

### v1.0.2
- Fixed update feature connection error handling
- Better user feedback when cPanel restarts during update

### v1.0.1
- Added backup management with restore functionality
- Added backup filtering by type (plugin/theme)
- Added individual backup deletion
- Added auto-update feature from GitHub
- Added version display in WHM interface

### v1.0.0
- Initial release
- Bulk plugin/theme updates
- Optional backup before update
- WHM status and uninstall interface

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please open an issue on GitHub:
https://github.com/ryonwhyte/simplify-manual-wp-actions/issues
