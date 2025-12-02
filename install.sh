#!/bin/bash

###############################################################################
# Simplify Manual WP Actions - cPanel Plugin Installation Script
###############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
   exit 1
fi

echo "======================================"
echo " Simplify Manual WP Actions"
echo " WHM + cPanel Plugin Installation"
echo "======================================"
echo ""

# Create directories
log_info "Creating directories..."
mkdir -p /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions
mkdir -p /var/log/simplify_manual_wp_actions
mkdir -p /var/cache/simplify_manual_wp_actions
mkdir -p /var/cache/simplify_manual_wp_actions/backups
mkdir -p /var/cache/simplify_manual_wp_actions/temp

# Set permissions on cache and log directories
chown root:root /var/log/simplify_manual_wp_actions
chmod 0777 /var/log/simplify_manual_wp_actions
chown root:root /var/cache/simplify_manual_wp_actions
chmod 0755 /var/cache/simplify_manual_wp_actions
chmod 0777 /var/cache/simplify_manual_wp_actions/backups
chmod 0777 /var/cache/simplify_manual_wp_actions/temp

# Function to clear all caches
clear_all_caches() {
    log_info "Clearing all cPanel caches..."

    # Clear system-level caches
    rm -rf /usr/local/cpanel/base/frontend/jupiter/.cpanelcache/* 2>/dev/null || true
    rm -rf /usr/local/cpanel/base/frontend/paper_lantern/.cpanelcache/* 2>/dev/null || true

    # Clear user-level caches for ALL users
    for userdir in /home/*; do
        if [ -d "$userdir/.cpanel/caches" ]; then
            rm -rf "$userdir/.cpanel/caches/dynamicui/"* 2>/dev/null || true
        fi
    done

    # Clear root user cache
    rm -rf /root/.cpanel/caches/dynamicui/* 2>/dev/null || true
}

# Clear caches BEFORE installation
clear_all_caches

# Clean up any old dynamicui configurations
log_info "Cleaning up old dynamicui configurations..."
rm -f /usr/local/cpanel/base/frontend/jupiter/dynamicui/dynamicui_simplify_manual_wp_actions.conf 2>/dev/null || true
rm -f /usr/local/cpanel/base/frontend/paper_lantern/dynamicui/dynamicui_simplify_manual_wp_actions.conf 2>/dev/null || true

# Create plugin directories for both themes
mkdir -p /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/base/frontend/jupiter/dynamicui
mkdir -p /usr/local/cpanel/base/frontend/paper_lantern/dynamicui

# Install CGI backend to 3rdparty directory (for proper execution context)
log_info "Installing CGI backend..."
install -m 755 cpanel/index.cgi /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions/

# Install to both Jupiter and Paper Lantern themes
for theme in jupiter paper_lantern; do
    log_info "Installing for $theme theme..."

    # Install the live.pl wrapper script (entry point from dynamicui)
    install -m 755 cpanel/index.live.pl /usr/local/cpanel/base/frontend/$theme/simplify_manual_wp_actions/

    # Install the HTML template
    install -m 644 cpanel/index.html.tt /usr/local/cpanel/base/frontend/$theme/simplify_manual_wp_actions/

    # Install icon
    install -m 644 cpanel/simplify_manual_wp_actions.svg /usr/local/cpanel/base/frontend/$theme/simplify_manual_wp_actions/
done

# Use install_plugin script to properly register the plugin
log_info "Creating plugin package for install_plugin..."
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/simplify_manual_wp_actions"

# Copy install.json to root
cp cpanel/install.json "$TEMP_DIR/install.json"

# Copy plugin files
cp cpanel/index.live.pl "$TEMP_DIR/simplify_manual_wp_actions/"
cp cpanel/index.html.tt "$TEMP_DIR/simplify_manual_wp_actions/"
cp cpanel/simplify_manual_wp_actions.svg "$TEMP_DIR/simplify_manual_wp_actions/"

# Create tarball
cd "$TEMP_DIR"
tar -czf simplify_manual_wp_actions.tar.gz install.json simplify_manual_wp_actions/
cd - >/dev/null

# Install using official script for both themes
log_info "Installing cPanel plugin using install_plugin..."
/usr/local/cpanel/scripts/install_plugin "$TEMP_DIR/simplify_manual_wp_actions.tar.gz" --theme jupiter 2>/dev/null || true

if [ -d "/usr/local/cpanel/base/frontend/paper_lantern" ]; then
    /usr/local/cpanel/scripts/install_plugin "$TEMP_DIR/simplify_manual_wp_actions.tar.gz" --theme paper_lantern 2>/dev/null || true
fi

rm -rf "$TEMP_DIR"

# ALWAYS create dynamicui configuration manually (legacy format for better compatibility)
log_info "Creating dynamicui configuration (legacy format)..."

for theme in jupiter paper_lantern; do
    if [ -d "/usr/local/cpanel/base/frontend/$theme/dynamicui" ]; then
        cat > "/usr/local/cpanel/base/frontend/$theme/dynamicui/dynamicui_simplify_manual_wp_actions.conf" <<'EOF'
description=>Simplify Manual WP Actions,feature=>,file=>simplify_manual_wp_actions,group=>domains,height=>48,imgtype=>icon,itemdesc=>Simplify Manual WP Actions,itemorder=>1001,subtype=>img,target=>_self,type=>image,url=>simplify_manual_wp_actions/index.live.pl,width=>48
EOF
        chmod 644 "/usr/local/cpanel/base/frontend/$theme/dynamicui/dynamicui_simplify_manual_wp_actions.conf"
        log_info "Created dynamicui config for $theme"
    fi
done

# Clear all caches AFTER installation
clear_all_caches

# Rebuild sprites
log_info "Rebuilding sprites..."
/usr/local/cpanel/bin/rebuild_sprites 2>/dev/null || true

# Hard restart cPanel
log_info "Restarting cPanel service (hard restart)..."
/scripts/restartsrv_cpsrvd --hard

log_info "cPanel plugin registered successfully"

# Set proper ownership and permissions
log_info "Setting file permissions..."
chown -R root:root /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions
chown -R root:root /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions 2>/dev/null || true
chown -R root:root /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions
# Make scripts executable
chmod 755 /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions/index.live.pl
chmod 755 /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions/index.live.pl 2>/dev/null || true
chmod 755 /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions/index.cgi

# Install cleanup script for backups
log_info "Installing backup cleanup script..."
if [ -f "cleanup_backups.pl" ]; then
    install -m 755 cleanup_backups.pl /usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup

    # Set up cron job for automatic cleanup (runs daily at 3 AM)
    log_info "Setting up cron job for backup cleanup..."
    CRON_JOB="0 3 * * * /usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup >/dev/null 2>&1"
    (crontab -l 2>/dev/null | grep -v "simplify_manual_wp_actions_cleanup"; echo "$CRON_JOB") | crontab -
else
    log_warn "cleanup_backups.pl not found - skipping cron setup"
fi

###############################################################################
# WHM Plugin Installation
###############################################################################

log_info "Installing WHM plugin..."

# Create WHM directories
mkdir -p /usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/whostmgr/docroot/templates/simplify_manual_wp_actions
mkdir -p /usr/local/cpanel/whostmgr/docroot/addon_plugins

# Install WHM CGI script
if [ -f "whm/simplify_manual_wp_actions.cgi" ]; then
    install -m 755 whm/simplify_manual_wp_actions.cgi /usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions/
    log_info "Installed WHM CGI script"
else
    log_warn "WHM CGI script not found"
fi

# Install WHM template
if [ -f "whm/simplify_manual_wp_actions.tmpl" ]; then
    install -m 644 whm/simplify_manual_wp_actions.tmpl /usr/local/cpanel/whostmgr/docroot/templates/simplify_manual_wp_actions/
    log_info "Installed WHM template"
else
    log_warn "WHM template not found"
fi

# Install WHM icon
if [ -f "packaging/simplify_manual_wp_actions_icon.png" ]; then
    install -m 644 packaging/simplify_manual_wp_actions_icon.png /usr/local/cpanel/whostmgr/docroot/addon_plugins/
    log_info "Installed WHM icon"
else
    log_warn "WHM icon not found"
fi

# Register WHM AppConfig
if [ -f "packaging/simplify_manual_wp_actions.conf" ]; then
    install -m 644 packaging/simplify_manual_wp_actions.conf /var/cpanel/apps/
    /usr/local/cpanel/bin/register_appconfig /var/cpanel/apps/simplify_manual_wp_actions.conf 2>/dev/null || true
    log_info "Registered WHM AppConfig"
else
    log_warn "WHM AppConfig not found"
fi

# Set WHM file permissions
chown -R root:root /usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions 2>/dev/null || true
chown -R root:root /usr/local/cpanel/whostmgr/docroot/templates/simplify_manual_wp_actions 2>/dev/null || true
chmod 755 /usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions/simplify_manual_wp_actions.cgi 2>/dev/null || true

echo ""
echo "======================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "======================================"
echo ""
echo "Access the plugin:"
echo "  WHM:    WHM → Plugins → Simplify Manual WP Actions"
echo "  cPanel: cPanel → Domains → Simplify Manual WP Actions"
echo ""
echo "Features:"
echo "  • WHM: View status, uninstall plugin"
echo "  • cPanel: Bulk update plugins/themes across WordPress sites"
echo "  • Manual zip upload for plugin/theme updates"
echo "  • Optional backup before updating (14-day retention)"
echo "  • Real-time progress display"
echo ""
echo "Logs:"
echo "  • Plugin log: /var/log/simplify_manual_wp_actions/cpanel_<username>.log"
echo ""
echo "======================================"
echo -e "${GREEN}Verification${NC}"
echo "======================================"

# Verify WHM installation
WHM_SUCCESS=true
if [ -f "/usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions/simplify_manual_wp_actions.cgi" ]; then
    echo -e "${GREEN}✓${NC} WHM CGI script installed"
else
    echo -e "${RED}✗${NC} WHM CGI script NOT found"
    WHM_SUCCESS=false
fi

if [ -f "/var/cpanel/apps/simplify_manual_wp_actions.conf" ]; then
    echo -e "${GREEN}✓${NC} WHM AppConfig registered"
else
    echo -e "${RED}✗${NC} WHM AppConfig NOT found"
    WHM_SUCCESS=false
fi

# Verify cPanel installation
CPANEL_SUCCESS=true
if [ -f "/usr/local/cpanel/base/frontend/jupiter/dynamicui/dynamicui_simplify_manual_wp_actions.conf" ]; then
    echo -e "${GREEN}✓${NC} cPanel dynamicui config installed"
else
    echo -e "${RED}✗${NC} cPanel dynamicui config NOT found"
    CPANEL_SUCCESS=false
fi

if [ -f "/usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions/index.live.pl" ]; then
    echo -e "${GREEN}✓${NC} cPanel plugin files installed"
else
    echo -e "${RED}✗${NC} cPanel plugin files NOT found"
    CPANEL_SUCCESS=false
fi

if [ -f "/usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions/simplify_manual_wp_actions.svg" ]; then
    echo -e "${GREEN}✓${NC} cPanel icons installed"
else
    echo -e "${RED}✗${NC} cPanel icons NOT found"
    CPANEL_SUCCESS=false
fi

echo ""
echo "======================================"
echo "IMPORTANT - Next Steps:"
echo "======================================"
echo ""
if [ "$WHM_SUCCESS" = true ] && [ "$CPANEL_SUCCESS" = true ]; then
    echo -e "${GREEN}WHM + cPanel Plugin is ready!${NC}"
    echo ""
    echo "To access the plugin:"
    echo "  WHM:"
    echo "    1. Log into WHM"
    echo "    2. Look in Plugins section for 'Simplify Manual WP Actions'"
    echo ""
    echo "  cPanel:"
    echo "    1. Log out of cPanel completely"
    echo "    2. Clear browser cache (Ctrl+Shift+Del)"
    echo "    3. Log back into cPanel"
    echo "    4. Look in Domains section for 'Simplify Manual WP Actions'"
else
    echo -e "${RED}Plugin installation may have issues.${NC}"
    echo "Please check the errors above and try reinstalling."
fi
echo ""
echo "Direct URLs:"
echo "  WHM:    https://yourserver:2087/cgi/simplify_manual_wp_actions/simplify_manual_wp_actions.cgi"
echo "  cPanel: https://yourserver:2083/frontend/jupiter/simplify_manual_wp_actions/index.live.pl"
echo ""
