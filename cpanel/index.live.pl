#!/usr/local/cpanel/3rdparty/bin/perl

# Simplify Manual WP Actions - cPanel Plugin Entry Point
# This script redirects to the Template Toolkit file for proper rendering

use strict;
use warnings;

# The template file is in the same directory as this script
# Just redirect to it directly with a relative path
print "Status: 302 Found\r\n";
print "Location: index.html.tt\r\n\r\n";

1;
