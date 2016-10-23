# servercanary

Version 0.3

Listen on a port and give simple server health check messages.

Returns 200 if ok, 500 if not, with a JSON output.

Particularly useful for AWS ELB health checkers.

# Install

- pip install psutil
- pip install daemon

# Usage

Run from commandline as a daemon

Expects a config file in /etc/canaryserver.cfg.  Another file can be specified with -f commandline option

# Config file

Format:

    command:arg

Commands:

    ps - Check for string <arg> in the ps table

    port - See if something is listening on port <arg>

    pidfile - Check to see if pidfile is valid and running

# Output

{
    'status': 'error|ok',
    'issues': [
        "port: port is not bound '8003'",
        "ps: could not find process 'postgres'"
    ],
    'datetime': 'date time TZ:timezone'
}
