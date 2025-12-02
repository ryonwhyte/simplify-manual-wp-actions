#!/usr/bin/perl

###############################################################################
# Simplify Manual WP Actions - Backup Cleanup Script
# Deletes backups older than 14 days
# Run via cron: 0 3 * * * /usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup
###############################################################################

use strict;
use warnings;
use File::Path qw(remove_tree);

my $BACKUP_DIR = '/var/cache/simplify_manual_wp_actions/backups';
my $TEMP_DIR = '/var/cache/simplify_manual_wp_actions/temp';
my $LOG_DIR = '/var/log/simplify_manual_wp_actions';
my $RETENTION_DAYS = 14;
my $TEMP_RETENTION_HOURS = 24;

# Calculate cutoff times
my $backup_cutoff = time() - ($RETENTION_DAYS * 24 * 60 * 60);
my $temp_cutoff = time() - ($TEMP_RETENTION_HOURS * 60 * 60);

my $deleted_backups = 0;
my $deleted_temp = 0;
my @errors;

# Cleanup old backups
if (-d $BACKUP_DIR) {
    opendir(my $dh, $BACKUP_DIR) or die "Cannot open $BACKUP_DIR: $!";
    my @files = grep { /\.zip$/ && -f "$BACKUP_DIR/$_" } readdir($dh);
    closedir($dh);

    foreach my $file (@files) {
        my $path = "$BACKUP_DIR/$file";
        my $mtime = (stat($path))[9];

        if ($mtime < $backup_cutoff) {
            if (unlink($path)) {
                $deleted_backups++;
            } else {
                push @errors, "Failed to delete backup: $path - $!";
            }
        }
    }
}

# Cleanup old temp directories
if (-d $TEMP_DIR) {
    opendir(my $dh, $TEMP_DIR) or die "Cannot open $TEMP_DIR: $!";
    my @dirs = grep { /^[a-f0-9]{32}$/ && -d "$TEMP_DIR/$_" } readdir($dh);
    closedir($dh);

    foreach my $dir (@dirs) {
        my $path = "$TEMP_DIR/$dir";
        my $mtime = (stat($path))[9];

        if ($mtime < $temp_cutoff) {
            my $removed = remove_tree($path, { safe => 1 });
            if ($removed > 0) {
                $deleted_temp++;
            } else {
                push @errors, "Failed to delete temp dir: $path";
            }
        }
    }
}

# Log results
my $timestamp = scalar localtime(time());
my $log_file = "$LOG_DIR/cleanup.log";

unless (-d $LOG_DIR) {
    mkdir($LOG_DIR, 0755);
}

if (open my $fh, '>>', $log_file) {
    print $fh "[$timestamp] Cleanup completed: deleted $deleted_backups backup(s), $deleted_temp temp dir(s)\n";

    if (@errors) {
        foreach my $error (@errors) {
            print $fh "[$timestamp] ERROR: $error\n";
        }
    }

    close $fh;
}

# Print summary (for cron output if verbose)
print "Cleanup completed: deleted $deleted_backups backup(s), $deleted_temp temp dir(s)\n";
if (@errors) {
    print "Errors:\n";
    print "  - $_\n" for @errors;
}

exit(0);
