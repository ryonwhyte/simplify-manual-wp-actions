#!/usr/bin/sh
eval 'if [ -x /usr/local/cpanel/3rdparty/bin/perl ]; then exec /usr/local/cpanel/3rdparty/bin/perl -x -- $0 ${1+"$@"}; else exec /usr/bin/perl -x -- $0 ${1+"$@"};fi'
if 0;
#!/usr/bin/perl

#WHMADDON:simplify_manual_wp_actions:Simplify Manual WP Actions
#ACLS:all

use strict;
use warnings;
use lib '/usr/local/cpanel';
use Whostmgr::ACLS();
use Cpanel::JSON();
use File::Path qw(remove_tree);

Whostmgr::ACLS::init_acls();

# Constants
my $CACHE_DIR = '/var/cache/simplify_manual_wp_actions';
my $BACKUP_DIR = "$CACHE_DIR/backups";
my $LOG_DIR = '/var/log/simplify_manual_wp_actions';

run() unless caller();

sub run {
    my $request_method = $ENV{REQUEST_METHOD} || 'GET';

    # Check permissions
    if (!Whostmgr::ACLS::hasroot()) {
        if ($request_method eq 'POST') {
            print_json_error('access_denied', 'Root access required');
        } else {
            print_html_error('Access Denied', 'You do not have access to this plugin.');
        }
        exit;
    }

    # Handle POST requests (API calls)
    if ($request_method eq 'POST') {
        handle_api_request();
    } else {
        # Handle GET requests (UI rendering)
        render_ui();
    }

    exit;
}

###############################################################################
# API Request Handler
###############################################################################

sub handle_api_request {
    my $post_body = '';
    if (!eof(STDIN)) {
        local $/;
        $post_body = <STDIN>;
    }

    unless ($post_body && $post_body ne '') {
        print_json_error('invalid_json', 'Empty request body');
        return;
    }

    my $request = eval { Cpanel::JSON::Load($post_body) };
    if ($@) {
        print_json_error('invalid_json', "Invalid JSON: $@");
        return;
    }

    my $action = $request->{action} || '';

    if ($action eq 'get_status') {
        get_status();
    }
    elsif ($action eq 'uninstall') {
        do_uninstall();
    }
    else {
        print_json_error('unknown_action', "Unknown action: $action");
    }
}

###############################################################################
# Get Plugin Status
###############################################################################

sub get_status {
    my %status = (
        installed => 0,
        backup_count => 0,
        backup_size => 0,
        backup_size_formatted => '0 Bytes',
        log_files => [],
        cpanel_installed => 0,
    );

    # Check if cPanel plugin is installed
    if (-f '/usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions/index.live.pl') {
        $status{installed} = 1;
        $status{cpanel_installed} = 1;
    }

    # Count backups
    if (-d $BACKUP_DIR) {
        opendir(my $dh, $BACKUP_DIR);
        my @backups = grep { /\.zip$/ && -f "$BACKUP_DIR/$_" } readdir($dh);
        closedir($dh);

        $status{backup_count} = scalar(@backups);

        my $total_size = 0;
        foreach my $file (@backups) {
            $total_size += (stat("$BACKUP_DIR/$file"))[7] || 0;
        }
        $status{backup_size} = $total_size;
        $status{backup_size_formatted} = format_bytes($total_size);
    }

    # List log files
    if (-d $LOG_DIR) {
        opendir(my $dh, $LOG_DIR);
        my @logs = grep { /\.log$/ && -f "$LOG_DIR/$_" } readdir($dh);
        closedir($dh);
        $status{log_files} = \@logs;
    }

    # Check cron job
    my $cron_output = `crontab -l 2>/dev/null | grep simplify_manual_wp_actions_cleanup`;
    $status{cron_installed} = ($cron_output =~ /simplify_manual_wp_actions/) ? 1 : 0;

    print_json_success(\%status);
}

###############################################################################
# Uninstall Plugin
###############################################################################

sub do_uninstall {
    my @results;
    my $errors = 0;

    # Remove cPanel files
    my @cpanel_dirs = (
        '/usr/local/cpanel/base/frontend/jupiter/simplify_manual_wp_actions',
        '/usr/local/cpanel/base/frontend/paper_lantern/simplify_manual_wp_actions',
        '/usr/local/cpanel/base/3rdparty/simplify_manual_wp_actions',
    );

    foreach my $dir (@cpanel_dirs) {
        if (-d $dir) {
            my $removed = remove_tree($dir, { safe => 1 });
            if ($removed > 0 || !-d $dir) {
                push @results, "Removed: $dir";
            } else {
                push @results, "Failed to remove: $dir";
                $errors++;
            }
        }
    }

    # Remove dynamicui configs
    my @dynamicui_files = (
        '/usr/local/cpanel/base/frontend/jupiter/dynamicui/dynamicui_simplify_manual_wp_actions.conf',
        '/usr/local/cpanel/base/frontend/paper_lantern/dynamicui/dynamicui_simplify_manual_wp_actions.conf',
    );

    foreach my $file (@dynamicui_files) {
        if (-f $file) {
            if (unlink($file)) {
                push @results, "Removed: $file";
            } else {
                push @results, "Failed to remove: $file";
                $errors++;
            }
        }
    }

    # Remove WHM files
    my @whm_files = (
        '/usr/local/cpanel/whostmgr/docroot/cgi/simplify_manual_wp_actions',
        '/usr/local/cpanel/whostmgr/docroot/templates/simplify_manual_wp_actions',
    );

    foreach my $path (@whm_files) {
        if (-d $path) {
            my $removed = remove_tree($path, { safe => 1 });
            push @results, "Removed: $path" if $removed > 0;
        } elsif (-f $path) {
            unlink($path) and push @results, "Removed: $path";
        }
    }

    # Remove WHM icon
    if (-f '/usr/local/cpanel/whostmgr/docroot/addon_plugins/simplify_manual_wp_actions_icon.png') {
        unlink('/usr/local/cpanel/whostmgr/docroot/addon_plugins/simplify_manual_wp_actions_icon.png');
        push @results, "Removed WHM icon";
    }

    # Unregister WHM AppConfig
    if (-f '/var/cpanel/apps/simplify_manual_wp_actions.conf') {
        system('/usr/local/cpanel/bin/unregister_appconfig', '/var/cpanel/apps/simplify_manual_wp_actions.conf');
        unlink('/var/cpanel/apps/simplify_manual_wp_actions.conf');
        push @results, "Unregistered WHM AppConfig";
    }

    # Remove cleanup script
    if (-f '/usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup') {
        unlink('/usr/local/cpanel/scripts/simplify_manual_wp_actions_cleanup');
        push @results, "Removed cleanup script";
    }

    # Remove cron job
    my $cron_removed = system('bash', '-c', 'crontab -l 2>/dev/null | grep -v "simplify_manual_wp_actions_cleanup" | crontab - 2>/dev/null');
    push @results, "Removed cron job";

    # Remove log directory
    if (-d $LOG_DIR) {
        remove_tree($LOG_DIR, { safe => 1 });
        push @results, "Removed log directory";
    }

    # Remove cache directory (including backups)
    if (-d $CACHE_DIR) {
        remove_tree($CACHE_DIR, { safe => 1 });
        push @results, "Removed cache directory (including backups)";
    }

    # Restart cPanel
    system('/scripts/restartsrv_cpsrvd', '--hard');
    push @results, "Restarted cPanel service";

    print_json_success({
        success => $errors == 0 ? Cpanel::JSON::true : Cpanel::JSON::false,
        results => \@results,
        errors => $errors,
        message => $errors == 0 ? 'Plugin uninstalled successfully' : "Uninstall completed with $errors error(s)"
    });
}

###############################################################################
# Helpers
###############################################################################

sub format_bytes {
    my ($bytes) = @_;
    return '0 Bytes' unless $bytes;

    my @units = ('Bytes', 'KB', 'MB', 'GB');
    my $i = 0;
    while ($bytes >= 1024 && $i < $#units) {
        $bytes /= 1024;
        $i++;
    }
    return sprintf("%.2f %s", $bytes, $units[$i]);
}

sub render_ui {
    # Use Template Toolkit for proper WHM integration
    use Cpanel::Template ();

    print "Content-type: text/html\r\n\r\n";

    Cpanel::Template::process_template(
        'whostmgr',
        {
            'template_file' => 'simplify_manual_wp_actions/simplify_manual_wp_actions.tmpl',
            'print'         => 1,
        }
    );

    return;
}

sub print_json_success {
    my ($data) = @_;
    print "Content-Type: application/json\r\n\r\n";
    print Cpanel::JSON::Dump({ ok => Cpanel::JSON::true, data => $data });
}

sub print_json_error {
    my ($code, $message) = @_;
    print "Content-Type: application/json\r\n\r\n";
    print Cpanel::JSON::Dump({
        ok => Cpanel::JSON::false,
        error => { code => $code, message => $message }
    });
}

sub print_html_error {
    my ($title, $message) = @_;
    print "Content-Type: text/html\r\n\r\n";
    print "<h1>$title</h1>\n<p>$message</p>\n";
}

1;
