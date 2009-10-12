#
# Regular cron jobs for the pywinery package
#
0 4	* * *	root	[ -x /usr/bin/pywinery_maintenance ] && /usr/bin/pywinery_maintenance
