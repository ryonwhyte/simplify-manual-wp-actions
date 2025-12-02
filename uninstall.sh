#!/bin/bash

###############################################################################
# Simplify Manual WP Actions - Uninstallation Script
###############################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" >&2
}

# Check root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
   exit 1
fi

echo "======================================"
echo " Simplify Manual WP Actions"
echo " Uninstallation"
echo "======================================"
echo ""
echo "This will remove:"
echo "  • WHM plugin"
echo "  • cPanel plugin"
echo "  • All plugin files"
echo "  • Log and cache directories"
echo "  • Backup cleanup cron job"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Uninstallation cancelled"
    exit 0
fi

echo ""

# Remove WHM files
log_info "Removing WHM files..."
rm -rf /usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions
rm -rf /usr/local/cpanel/whostmgr/docroot/templates/simplify_manual_wp_actions
rm -f /usr/local/cpanel/whostmgr/docroot/addon_plugins/simplify_manual_wp_actions_icon.png

# Unregister WHM AppConfig
log_info "Unregistering WHM AppConfig..."
if [ -f /var/cpanel/apps/simplify_manual_wp_actions.conf ]; then
    /usr/local/cpanel/bin/unregister_appconfig /var/cpanel/apps/simplify_manual_wp_actions.conf 2>/dev/null || true
    rm -f /var/cpanel/apps/simplify_manual_wp_actions.conf
fi

# Remove cPanel files
log_info "Removing cPanel files..."
rm -rf /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions
rm -rf /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions
rm -rf /usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions

# Remove from dynamicui registry
log_info "Removing from dynamicui registry..."
rm -f /usr/local/cpanel/base/frontend/jupiter/dynamicui/dynamicui_simplify_manual_wp_actions.conf
rm -f /usr/local/cpanel/base/frontend/paper_lantern/dynamicui/dynamicui_simplify_manual_wp_actions.conf

# Clear ALL caches comprehensively
log_info "Clearing all cPanel caches..."

# System-level caches
rm -rf /usr/local/cpanel/base/frontend/jupiter/dynamicui_data/* 2>/dev/null || true
rm -rf /usr/local/cpanel/base/frontend/jupiter/.dynamicui_cache 2>/dev/null || true
rm -rf /usr/local/cpanel/base/frontend/jupiter/.cpanelcache/* 2>/dev/null || true
rm -rf /usr/local/cpanel/base/frontend/paper_lantern/.cpanelcache/* 2>/dev/null || true

# User-level caches for ALL users
for userdir in /home/*; do
    if [ -d "$userdir/.cpanel" ]; then
        rm -rf "$userdir/.cpanel/caches/dynamicui/"* 2>/dev/null || true
        rm -rf "$userdir/.cpanel/dynamicui/"* 2>/dev/null || true
        rm -rf "$userdir/.cpanel/datastore/"* 2>/dev/null || true
        rm -rf "$userdir/.cpanel/nvdata/"* 2>/dev/null || true
    fi
done

# Root user cache
rm -rf /root/.cpanel/caches/dynamicui/* 2>/dev/null || true

# Other cache locations
rm -rf /var/cpanel/dynamicui/* 2>/dev/null || true

# Rebuild dynamicui after removal
log_info "Rebuilding dynamicui..."
if [ -x /usr/local/cpanel/scripts/build_jupiter_dynamicui ]; then
    /usr/local/cpanel/scripts/build_jupiter_dynamicui
fi

# Remove log directory
log_info "Removing log directory..."
rm -rf /var/log/simplify_manual_wp_actions

# Remove cache directory (including backups)
log_info "Removing cache directory..."
rm -rf /var/cache/simplify_manual_wp_actions

# Remove cleanup script
log_info "Removing cleanup script..."
rm -f /usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup

# Remove cron job
log_info "Removing cron job..."
crontab -l 2>/dev/null | grep -v "simplify_manual_wp_actions_cleanup" | crontab - 2>/dev/null || true

# Verify removal
echo ""
log_info "Verifying removal..."

ERRORS=0

if [ -d /usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions ]; then
    log_error "cPanel Jupiter directory still exists"
    ERRORS=$((ERRORS + 1))
fi

if [ -d /usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions ]; then
    log_error "cPanel Paper Lantern directory still exists"
    ERRORS=$((ERRORS + 1))
fi

if [ -d /var/log/simplify_manual_wp_actions ]; then
    log_error "Log directory still exists"
    ERRORS=$((ERRORS + 1))
fi

if [ -d /var/cache/simplify_manual_wp_actions ]; then
    log_error "Cache directory still exists"
    ERRORS=$((ERRORS + 1))
fi

if [ $ERRORS -eq 0 ]; then
    log_info "All files removed successfully"
else
    log_error "$ERRORS file(s) could not be removed"
    echo ""
    echo "You may need to manually remove remaining files"
    exit 1
fi

# Rebuild sprites
log_info "Rebuilding sprites..."
/usr/local/cpanel/bin/rebuild_sprites 2>/dev/null || true

# Restart services
echo ""
log_info "Restarting cpsrvd (hard restart)..."
/scripts/restartsrv_cpsrvd --hard

echo ""
echo "======================================"
echo -e "${GREEN}Uninstallation Complete!${NC}"
echo "======================================"
echo ""
echo "All Simplify Manual WP Actions plugin"
echo "files have been removed from the system."
echo ""
