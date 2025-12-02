#!/usr/bin/sh
eval 'if [ -x /usr/local/cpanel/3rdparty/bin/perl ]; then exec /usr/local/cpanel/3rdparty/bin/perl -x -- $0 ${1+"$@"}; else exec /usr/bin/perl -x -- $0 ${1+"$@"};fi'
if 0;
#!/usr/bin/perl

###############################################################################
# Simplify Manual WP Actions - cPanel Plugin Backend
# Bulk update WordPress plugins/themes across multiple sites
###############################################################################

use strict;
use warnings;
use lib '/usr/local/cpanel';
use Cpanel::JSON();
use CGI();
use File::Basename;
use File::Copy;
use File::Path qw(make_path remove_tree);
use Cwd 'realpath';
use Archive::Zip qw(:ERROR_CODES :CONSTANTS);
use Digest::MD5 qw(md5_hex);

# Constants
my $MAX_UPLOAD_SIZE = 50 * 1024 * 1024;  # 50 MB
my $CACHE_DIR = '/var/cache/simplify_manual_wp_actions';
my $BACKUP_DIR = "$CACHE_DIR/backups";
my $TEMP_DIR = "$CACHE_DIR/temp";
my $LOG_DIR = '/var/log/simplify_manual_wp_actions';
my $BACKUP_RETENTION_DAYS = 14;

run() unless caller();

sub run {
    my $request_method = $ENV{REQUEST_METHOD} || 'GET';

    # Get authenticated user
    my $cpanel_user = $ENV{REMOTE_USER} || '';
    unless ($cpanel_user) {
        if ($request_method eq 'POST') {
            print_json_error('not_authenticated', 'Authentication required');
        } else {
            print_html_error('Not Authenticated', 'You must be logged into cPanel.');
        }
        exit;
    }

    # Handle POST requests (API calls)
    if ($request_method eq 'POST') {
        handle_api_request($cpanel_user);
    } else {
        # For GET requests, show error - should use template
        render_ui($cpanel_user);
    }

    exit;
}

###############################################################################
# API Request Handler
###############################################################################

sub handle_api_request {
    my ($cpanel_user) = @_;

    # Check content type for multipart (file upload)
    my $content_type = $ENV{CONTENT_TYPE} || '';

    if ($content_type =~ /multipart\/form-data/) {
        # Handle file upload
        handle_file_upload($cpanel_user);
        return;
    }

    # Handle JSON API requests
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
    my $payload = $request->{payload} || {};

    # Route to appropriate handler
    if ($action eq 'health') {
        print_json_success({ status => 'ok', user => $cpanel_user });
    }
    elsif ($action eq 'scan_wordpress') {
        my $force_scan = $payload->{force_scan} || 0;
        my $sites = scan_wordpress($cpanel_user, $force_scan);
        print_json_success($sites);
    }
    elsif ($action eq 'load_cached_wordpress') {
        my $cached = load_cached_wordpress_scan($cpanel_user);
        print_json_success($cached);
    }
    elsif ($action eq 'detect_installed') {
        my $result = detect_installed($cpanel_user, $payload);
        print_json_success($result);
    }
    elsif ($action eq 'update_site') {
        update_site($cpanel_user, $payload);
    }
    elsif ($action eq 'cleanup_temp') {
        cleanup_temp($cpanel_user, $payload);
    }
    elsif ($action eq 'list_backups') {
        my $backups = list_backups($cpanel_user);
        print_json_success($backups);
    }
    elsif ($action eq 'delete_all_backups') {
        delete_all_backups($cpanel_user);
    }
    else {
        print_json_error('unknown_action', "Unknown action: $action");
    }
}

###############################################################################
# File Upload Handler
###############################################################################

sub handle_file_upload {
    my ($cpanel_user) = @_;

    # Use CGI module for multipart handling
    $CGI::POST_MAX = $MAX_UPLOAD_SIZE;
    my $cgi = CGI->new();

    # Check for upload errors
    if ($cgi->cgi_error()) {
        print_json_error('upload_error', $cgi->cgi_error());
        return;
    }

    # Get uploaded file
    my $fh = $cgi->upload('zipfile');
    unless ($fh) {
        print_json_error('no_file', 'No file uploaded');
        return;
    }

    # Get update type (plugin or theme)
    my $update_type = $cgi->param('update_type') || 'plugin';
    unless ($update_type eq 'plugin' || $update_type eq 'theme') {
        print_json_error('invalid_type', 'Update type must be plugin or theme');
        return;
    }

    # Create temp directory for extraction
    my $temp_id = md5_hex($cpanel_user . time() . rand());
    my $temp_path = "$TEMP_DIR/$temp_id";
    make_path($temp_path);

    # Save uploaded file
    my $zip_path = "$temp_path/upload.zip";
    if (open my $out, '>', $zip_path) {
        binmode $out;
        binmode $fh;
        while (my $chunk = <$fh>) {
            print $out $chunk;
        }
        close $out;
    } else {
        print_json_error('save_error', "Failed to save uploaded file: $!");
        return;
    }

    # Validate and extract zip
    my $zip = Archive::Zip->new();
    unless ($zip->read($zip_path) == AZ_OK) {
        remove_tree($temp_path);
        print_json_error('invalid_zip', 'Invalid or corrupted zip file');
        return;
    }

    # Security check: no path traversal in zip
    foreach my $member ($zip->members()) {
        my $name = $member->fileName();
        if ($name =~ /\.\./ || $name =~ /^\//) {
            remove_tree($temp_path);
            print_json_error('security_error', 'Zip contains invalid paths');
            return;
        }
    }

    # Extract zip
    my $extract_path = "$temp_path/extracted";
    make_path($extract_path);
    unless ($zip->extractTree('', $extract_path) == AZ_OK) {
        remove_tree($temp_path);
        print_json_error('extract_error', 'Failed to extract zip file');
        return;
    }

    # Find the plugin/theme folder (handle nested structure)
    my ($slug, $item_path) = find_item_folder($extract_path, $update_type);
    unless ($slug && $item_path) {
        remove_tree($temp_path);
        print_json_error('invalid_structure', "Could not find valid $update_type in zip file");
        return;
    }

    # Get item info
    my $item_info = get_item_info($item_path, $update_type);

    write_audit_log($cpanel_user, 'UPLOAD_ZIP', "type=$update_type slug=$slug", 'success');

    print_json_success({
        temp_id => $temp_id,
        temp_path => $temp_path,
        item_path => $item_path,
        slug => $slug,
        type => $update_type,
        name => $item_info->{name} || $slug,
        version => $item_info->{version} || 'unknown'
    });
}

###############################################################################
# Find Plugin/Theme Folder in Extracted Zip
###############################################################################

sub find_item_folder {
    my ($extract_path, $type) = @_;

    # First, get list of top-level directories
    opendir(my $dh, $extract_path) or return (undef, undef);
    my @dirs = grep { -d "$extract_path/$_" && !/^\./ } readdir($dh);
    closedir($dh);

    # If exactly one directory, check inside it
    if (@dirs == 1) {
        my $subdir = "$extract_path/$dirs[0]";

        # Check if this IS the plugin/theme folder
        if (is_valid_item($subdir, $type)) {
            return ($dirs[0], $subdir);
        }

        # Check if there's another folder inside (double-nested)
        opendir(my $dh2, $subdir) or return (undef, undef);
        my @subdirs = grep { -d "$subdir/$_" && !/^\./ } readdir($dh2);
        closedir($dh2);

        if (@subdirs == 1 && is_valid_item("$subdir/$subdirs[0]", $type)) {
            return ($subdirs[0], "$subdir/$subdirs[0]");
        }
    }

    # No valid structure found
    return (undef, undef);
}

sub is_valid_item {
    my ($path, $type) = @_;

    if ($type eq 'plugin') {
        # Check for PHP file with Plugin header
        opendir(my $dh, $path) or return 0;
        my @php_files = grep { /\.php$/ } readdir($dh);
        closedir($dh);

        foreach my $file (@php_files) {
            if (open my $fh, '<', "$path/$file") {
                my $content = '';
                read($fh, $content, 8192);  # Read first 8KB
                close $fh;

                if ($content =~ /Plugin\s*Name\s*:/i) {
                    return 1;
                }
            }
        }
    }
    elsif ($type eq 'theme') {
        # Check for style.css with Theme header
        my $style_css = "$path/style.css";
        if (-f $style_css && open my $fh, '<', $style_css) {
            my $content = '';
            read($fh, $content, 8192);
            close $fh;

            if ($content =~ /Theme\s*Name\s*:/i) {
                return 1;
            }
        }
    }

    return 0;
}

###############################################################################
# Get Plugin/Theme Info from Files
###############################################################################

sub get_item_info {
    my ($path, $type) = @_;

    my %info = (name => '', version => '');

    if ($type eq 'plugin') {
        # Find main plugin file
        opendir(my $dh, $path) or return \%info;
        my @php_files = grep { /\.php$/ } readdir($dh);
        closedir($dh);

        foreach my $file (@php_files) {
            if (open my $fh, '<', "$path/$file") {
                my $content = '';
                read($fh, $content, 8192);
                close $fh;

                if ($content =~ /Plugin\s*Name\s*:\s*(.+)/i) {
                    $info{name} = trim($1);
                }
                if ($content =~ /Version\s*:\s*(.+)/i) {
                    $info{version} = trim($1);
                }

                last if $info{name};
            }
        }
    }
    elsif ($type eq 'theme') {
        my $style_css = "$path/style.css";
        if (-f $style_css && open my $fh, '<', $style_css) {
            my $content = '';
            read($fh, $content, 8192);
            close $fh;

            if ($content =~ /Theme\s*Name\s*:\s*(.+)/i) {
                $info{name} = trim($1);
            }
            if ($content =~ /Version\s*:\s*(.+)/i) {
                $info{version} = trim($1);
            }
        }
    }

    return \%info;
}

###############################################################################
# Detect Installed Plugins/Themes on Sites
###############################################################################

sub detect_installed {
    my ($cpanel_user, $payload) = @_;

    my $sites = $payload->{sites} || [];
    my $type = $payload->{type} || 'plugin';
    my $slug = $payload->{slug} || '';

    unless (@$sites && $slug) {
        return { sites => [] };
    }

    my $homedir = (getpwnam($cpanel_user))[7];
    return { sites => [] } unless $homedir;

    my @results;
    my $wp = get_wp_cli_path();

    foreach my $site (@$sites) {
        my $site_path = $site->{path};

        # Validate path is under user's home
        next unless $site_path =~ /^\Q$homedir\E\//;
        next unless -d $site_path;

        my $is_installed = 0;
        my $current_version = '';

        # Use WP-CLI to check if plugin/theme is installed
        my $cmd;
        if ($type eq 'plugin') {
            $cmd = qq{$wp plugin list --path="$site_path" --format=json 2>/dev/null};
        } else {
            $cmd = qq{$wp theme list --path="$site_path" --format=json 2>/dev/null};
        }

        my ($output, $exit_code) = run_wp_cli($cmd);

        if ($exit_code == 0 && $output) {
            my $items = eval { Cpanel::JSON::Load($output) } || [];
            foreach my $item (@$items) {
                my $item_slug = $item->{name} || '';
                if ($item_slug eq $slug) {
                    $is_installed = 1;
                    $current_version = $item->{version} || '';
                    last;
                }
            }
        }

        push @results, {
            path => $site_path,
            domain => $site->{domain},
            is_installed => $is_installed ? Cpanel::JSON::true : Cpanel::JSON::false,
            current_version => $current_version
        };
    }

    return { sites => \@results };
}

###############################################################################
# Update Single Site
###############################################################################

sub update_site {
    my ($cpanel_user, $payload) = @_;

    my $site_path = $payload->{site_path} || '';
    my $temp_path = $payload->{temp_path} || '';
    my $item_path = $payload->{item_path} || '';
    my $slug = $payload->{slug} || '';
    my $type = $payload->{type} || 'plugin';
    my $create_backup = $payload->{create_backup} || 0;

    # Validate required params
    unless ($site_path && $temp_path && $item_path && $slug) {
        print_json_error('missing_params', 'Missing required parameters');
        return;
    }

    # Validate site path is under user's home
    my $homedir = (getpwnam($cpanel_user))[7];
    unless ($site_path =~ /^\Q$homedir\E\//) {
        print_json_error('invalid_path', 'Invalid site path');
        return;
    }

    # Validate temp_path is under our temp directory
    unless ($temp_path =~ /^\Q$TEMP_DIR\E\//) {
        print_json_error('invalid_temp_path', 'Invalid temp path');
        return;
    }

    # Determine target directory
    my $content_dir;
    if ($type eq 'plugin') {
        $content_dir = "$site_path/wp-content/plugins";
    } else {
        $content_dir = "$site_path/wp-content/themes";
    }

    unless (-d $content_dir) {
        print_json_error('invalid_site', "WordPress $type directory not found");
        return;
    }

    my $target_path = "$content_dir/$slug";

    # Check if the plugin/theme exists (we only update, never install new)
    unless (-d $target_path) {
        print_json_error('not_installed', "$type '$slug' is not installed on this site");
        return;
    }

    # Create backup if requested
    my $backup_path = '';
    if ($create_backup) {
        $backup_path = create_backup($cpanel_user, $site_path, $target_path, $slug, $type);
        unless ($backup_path) {
            print_json_error('backup_failed', 'Failed to create backup');
            return;
        }
    }

    # Remove existing plugin/theme
    my $removed = remove_tree($target_path, { safe => 1 });
    unless ($removed > 0 || !-d $target_path) {
        write_audit_log($cpanel_user, 'UPDATE_FAILED', "site=$site_path slug=$slug", 'Failed to remove old version');
        print_json_error('remove_failed', 'Failed to remove existing version');
        return;
    }

    # Copy new version
    my $copy_result = copy_directory($item_path, $target_path);
    unless ($copy_result) {
        write_audit_log($cpanel_user, 'UPDATE_FAILED', "site=$site_path slug=$slug", 'Failed to copy new version');
        print_json_error('copy_failed', 'Failed to copy new version');
        return;
    }

    # Set correct ownership (match the wp-content directory owner)
    my @stat = stat($content_dir);
    my $uid = $stat[4];
    my $gid = $stat[5];
    chown_recursive($target_path, $uid, $gid);

    write_audit_log($cpanel_user, 'UPDATE_SUCCESS', "site=$site_path slug=$slug type=$type", 'success');

    print_json_success({
        success => Cpanel::JSON::true,
        backup_path => $backup_path,
        message => "Successfully updated $slug"
    });
}

###############################################################################
# Create Backup
###############################################################################

sub create_backup {
    my ($cpanel_user, $site_path, $target_path, $slug, $type) = @_;

    make_path($BACKUP_DIR) unless -d $BACKUP_DIR;

    # Generate unique backup filename
    my $site_hash = substr(md5_hex($site_path), 0, 8);
    my $timestamp = time();
    my $backup_filename = "${site_hash}_${slug}_${timestamp}.zip";
    my $backup_path = "$BACKUP_DIR/$backup_filename";

    # Create zip backup
    my $zip = Archive::Zip->new();

    # Add directory recursively
    $zip->addTree($target_path, $slug);

    unless ($zip->writeToFileNamed($backup_path) == AZ_OK) {
        write_audit_log($cpanel_user, 'BACKUP_FAILED', "site=$site_path slug=$slug", "Failed to write zip");
        return '';
    }

    write_audit_log($cpanel_user, 'BACKUP_CREATED', "site=$site_path slug=$slug backup=$backup_filename", 'success');

    return $backup_path;
}

###############################################################################
# Copy Directory Recursively
###############################################################################

sub copy_directory {
    my ($src, $dst) = @_;

    return 0 unless -d $src;

    make_path($dst) unless -d $dst;

    opendir(my $dh, $src) or return 0;
    my @entries = readdir($dh);
    closedir($dh);

    foreach my $entry (@entries) {
        next if $entry eq '.' || $entry eq '..';

        my $src_path = "$src/$entry";
        my $dst_path = "$dst/$entry";

        if (-d $src_path) {
            return 0 unless copy_directory($src_path, $dst_path);
        } else {
            return 0 unless copy($src_path, $dst_path);
        }
    }

    return 1;
}

###############################################################################
# Chown Recursively
###############################################################################

sub chown_recursive {
    my ($path, $uid, $gid) = @_;

    return unless -e $path;

    chown $uid, $gid, $path;

    if (-d $path) {
        opendir(my $dh, $path) or return;
        my @entries = readdir($dh);
        closedir($dh);

        foreach my $entry (@entries) {
            next if $entry eq '.' || $entry eq '..';
            chown_recursive("$path/$entry", $uid, $gid);
        }
    }
}

###############################################################################
# Cleanup Temp Directory
###############################################################################

sub cleanup_temp {
    my ($cpanel_user, $payload) = @_;

    my $temp_path = $payload->{temp_path} || '';

    # Validate temp_path is under our temp directory
    if ($temp_path && $temp_path =~ /^\Q$TEMP_DIR\E\/[a-f0-9]{32}$/) {
        if (-d $temp_path) {
            remove_tree($temp_path);
            write_audit_log($cpanel_user, 'CLEANUP_TEMP', "path=$temp_path", 'success');
        }
    }

    print_json_success({ success => Cpanel::JSON::true });
}

###############################################################################
# WordPress Scanning (Reused from original plugin)
###############################################################################

sub get_cache_dir {
    my $cache_dir = $CACHE_DIR;
    unless (-d $cache_dir) {
        mkdir($cache_dir, 0750) or return undef;
    }
    return $cache_dir;
}

sub get_cache_file {
    my ($account) = @_;
    return undef unless $account;

    my $cache_dir = get_cache_dir();
    return undef unless $cache_dir;

    $account =~ s/[^a-zA-Z0-9_-]/_/g;
    return "$cache_dir/wp_scan_${account}.json";
}

sub save_cached_wordpress_scan {
    my ($account, $sites) = @_;
    return unless $account && $sites;

    my $cache_file = get_cache_file($account);
    return unless $cache_file;

    my $data = {
        account => $account,
        timestamp => time(),
        sites => $sites
    };

    if (open my $fh, '>', $cache_file) {
        print $fh Cpanel::JSON::Dump($data);
        close $fh;
        chmod 0640, $cache_file;
    }
}

sub load_cached_wordpress_scan {
    my ($account) = @_;
    return undef unless $account;

    my $cache_file = get_cache_file($account);
    return undef unless $cache_file && -f $cache_file;

    # Check cache age (valid for 1 hour)
    my $max_age = 3600;
    my $cache_mtime = (stat($cache_file))[9];
    if (time() - $cache_mtime > $max_age) {
        unlink $cache_file;
        return undef;
    }

    if (open my $fh, '<', $cache_file) {
        local $/;
        my $json = <$fh>;
        close $fh;

        my $data = eval { Cpanel::JSON::Load($json) };
        if ($data && $data->{sites}) {
            return $data->{sites};
        }
    }

    return undef;
}

sub scan_wordpress {
    my ($cpanel_user, $force_scan) = @_;

    unless ($force_scan) {
        my $cached = load_cached_wordpress_scan($cpanel_user);
        if ($cached && @$cached) {
            return $cached;
        }
    }

    my $homedir = (getpwnam($cpanel_user))[7];
    return [] unless $homedir && -d $homedir;

    my @sites;
    my @search_roots = (
        "$homedir/public_html",
        "$homedir/www",
        glob("$homedir/domains/*/public_html")
    );

    foreach my $root (@search_roots) {
        next unless -d $root;
        find_wordpress_recursive($root, $homedir, \@sites);
    }

    # Deduplicate using realpath
    my %seen_paths;
    my @unique_sites;
    foreach my $site (@sites) {
        my $real_path = realpath($site->{path}) || $site->{path};
        unless ($seen_paths{$real_path}++) {
            push @unique_sites, $site;
        }
    }

    save_cached_wordpress_scan($cpanel_user, \@unique_sites);

    return \@unique_sites;
}

sub find_wordpress_recursive {
    my ($dir, $homedir, $sites_ref) = @_;

    my $depth = ($dir =~ tr/\///);
    my $root_depth = ($homedir =~ tr/\///);
    return if ($depth - $root_depth) > 5;

    my $wp_config = "$dir/wp-config.php";
    if (-f $wp_config) {
        my $domain = extract_domain_from_path($dir, $homedir);
        my $site_url = extract_site_url($wp_config) || $domain;

        push @$sites_ref, {
            path => $dir,
            domain => $site_url,
            wp_config => $wp_config
        };
        return;
    }

    opendir(my $dh, $dir) or return;
    my @subdirs = grep {
        $_ ne '.' && $_ ne '..' &&
        -d "$dir/$_" &&
        $_ !~ /^\./ &&
        $_ ne 'wp-admin' &&
        $_ ne 'wp-content' &&
        $_ ne 'wp-includes'
    } readdir($dh);
    closedir($dh);

    foreach my $subdir (@subdirs) {
        find_wordpress_recursive("$dir/$subdir", $homedir, $sites_ref);
    }
}

sub extract_domain_from_path {
    my ($path, $homedir) = @_;

    my $relative = $path;
    $relative =~ s/^\Q$homedir\E\/?//;

    if ($relative =~ m|^domains/([^/]+)|) {
        return $1;
    }
    elsif ($relative =~ m|^public_html/([^/]+)|) {
        return $1;
    }
    elsif ($relative eq 'public_html' || $relative eq 'www') {
        return 'Main Site (public_html)';
    }

    return $relative || 'Unknown';
}

sub extract_site_url {
    my ($wp_config) = @_;

    if (open my $fh, '<', $wp_config) {
        while (my $line = <$fh>) {
            if ($line =~ /define\s*\(\s*['"](?:WP_SITEURL|WP_HOME)['"]\s*,\s*['"]([^'"]+)['"]/) {
                close $fh;
                my $url = $1;
                $url =~ s|^https?://||;
                $url =~ s|/$||;
                return $url;
            }
        }
        close $fh;
    }

    return undef;
}

###############################################################################
# WP-CLI Integration
###############################################################################

my $wp_cli_path_cache;

sub get_wp_cli_path {
    return $wp_cli_path_cache if $wp_cli_path_cache;

    my @possible_paths = (
        '/usr/local/bin/wp',
        '/usr/bin/wp',
        '/opt/cpanel/composer/bin/wp',
        '/usr/local/cpanel/3rdparty/bin/wp',
    );

    my $which_result = `which wp 2>/dev/null`;
    chomp $which_result;
    if ($which_result && -x $which_result) {
        $wp_cli_path_cache = $which_result;
        return $wp_cli_path_cache;
    }

    foreach my $path (@possible_paths) {
        if (-x $path) {
            $wp_cli_path_cache = $path;
            return $wp_cli_path_cache;
        }
    }

    $wp_cli_path_cache = 'wp';
    return $wp_cli_path_cache;
}

sub run_wp_cli {
    my ($cmd) = @_;

    my $current_user = $ENV{REMOTE_USER} || $ENV{USER} || 'nobody';
    my $homedir = (getpwnam($current_user))[7] || $ENV{HOME} || "/home/$current_user";

    $cmd = sprintf('env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=%s USER=%s %s',
        quotemeta($homedir),
        quotemeta($current_user),
        $cmd);

    my $output = `$cmd`;
    my $exit_code = $?;

    wantarray ? ($output, $exit_code) : $output;
}

###############################################################################
# Logging
###############################################################################

sub write_audit_log {
    my ($cpanel_user, $action, $details, $result) = @_;

    my $safe_username = $cpanel_user;
    $safe_username =~ s/[^a-zA-Z0-9_-]/_/g;

    my $log_file = "$LOG_DIR/cpanel_${safe_username}.log";

    unless (-d $LOG_DIR) {
        mkdir($LOG_DIR, 0777) or return;
    }

    $cpanel_user = sanitize_log_input($cpanel_user);
    $action = sanitize_log_input($action);
    $details = sanitize_log_input($details);
    $result = sanitize_log_input($result);

    my $timestamp = scalar localtime(time());
    my $remote_ip = $ENV{REMOTE_ADDR} || 'unknown';
    my $log_entry = sprintf("[%s] %s | %s | %s | %s | %s\n",
        $timestamp, $cpanel_user, $action, $details, $result, $remote_ip);

    if (open my $fh, '>>', $log_file) {
        print $fh $log_entry;
        close $fh;
        chmod 0640, $log_file;
    }
}

sub sanitize_log_input {
    my ($input) = @_;
    return '' unless defined $input;
    $input =~ s/[^\x20-\x7E]//g;
    return substr($input, 0, 500);
}

###############################################################################
# Backup Management
###############################################################################

sub list_backups {
    my ($cpanel_user) = @_;

    my @backups;
    my $total_size = 0;

    return { backups => [], total_size => 0, total_size_formatted => '0 Bytes' }
        unless -d $BACKUP_DIR;

    opendir(my $dh, $BACKUP_DIR) or return { backups => [], total_size => 0 };
    my @files = grep { /\.zip$/ && -f "$BACKUP_DIR/$_" } readdir($dh);
    closedir($dh);

    foreach my $file (sort { -M "$BACKUP_DIR/$a" <=> -M "$BACKUP_DIR/$b" } @files) {
        my $path = "$BACKUP_DIR/$file";
        my @stat = stat($path);
        my $size = $stat[7];
        my $mtime = $stat[9];

        $total_size += $size;

        # Parse filename: {site_hash}_{slug}_{timestamp}.zip
        my ($site_hash, $slug, $timestamp) = $file =~ /^([a-f0-9]+)_(.+)_(\d+)\.zip$/;

        push @backups, {
            filename => $file,
            size => $size,
            size_formatted => format_bytes($size),
            created => $mtime,
            created_formatted => scalar(localtime($mtime)),
            slug => $slug || 'unknown',
            age_days => int((time() - $mtime) / 86400)
        };
    }

    return {
        backups => \@backups,
        count => scalar(@backups),
        total_size => $total_size,
        total_size_formatted => format_bytes($total_size)
    };
}

sub delete_all_backups {
    my ($cpanel_user) = @_;

    my $deleted = 0;
    my @errors;

    if (-d $BACKUP_DIR) {
        opendir(my $dh, $BACKUP_DIR) or do {
            print_json_error('read_error', "Cannot read backup directory: $!");
            return;
        };
        my @files = grep { /\.zip$/ && -f "$BACKUP_DIR/$_" } readdir($dh);
        closedir($dh);

        foreach my $file (@files) {
            my $path = "$BACKUP_DIR/$file";
            if (unlink($path)) {
                $deleted++;
            } else {
                push @errors, "Failed to delete $file: $!";
            }
        }
    }

    write_audit_log($cpanel_user, 'DELETE_ALL_BACKUPS', "deleted=$deleted",
        @errors ? 'partial' : 'success');

    if (@errors) {
        print_json_success({
            success => Cpanel::JSON::false,
            deleted => $deleted,
            errors => \@errors,
            message => "Deleted $deleted backup(s), but some failed"
        });
    } else {
        print_json_success({
            success => Cpanel::JSON::true,
            deleted => $deleted,
            message => "Successfully deleted $deleted backup(s)"
        });
    }
}

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

###############################################################################
# Helpers
###############################################################################

sub trim {
    my ($str) = @_;
    return '' unless defined $str;
    $str =~ s/^\s+//;
    $str =~ s/\s+$//;
    return $str;
}

sub render_ui {
    my ($cpanel_user) = @_;

    print "Content-type: text/html\r\n\r\n";
    print qq{
        <!DOCTYPE html>
        <html>
        <head><title>Configuration Error</title></head>
        <body>
            <h1>Configuration Error</h1>
            <p>The cPanel plugin is not properly configured.</p>
            <p>Please access via the template file (index.html.tt).</p>
            <p>Current user: $cpanel_user</p>
        </body>
        </html>
    };
}

sub print_json_success {
    my ($data) = @_;
    print "X-No-SSI: 1\r\n";
    print "Content-Type: application/json\r\n\r\n";
    print Cpanel::JSON::Dump({ ok => Cpanel::JSON::true, data => $data });
}

sub print_json_error {
    my ($code, $message) = @_;
    print "X-No-SSI: 1\r\n";
    print "Content-Type: application/json\r\n\r\n";
    print Cpanel::JSON::Dump({
        ok => Cpanel::JSON::false,
        error => { code => $code, message => $message }
    });
}

sub print_html_error {
    my ($title, $message) = @_;
    print "Content-type: text/html; charset=utf-8\n\n";
    print "<h1>$title</h1>\n<p>$message</p>\n";
}

1;
