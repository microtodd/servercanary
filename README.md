# servercanary

Version 0.1

Listen on a port and give simple server health check messages.

Returns 200 if ok, 500 if not, with a JSON output.

Particularly useful for AWS ELB health checkers.

# Install

- pip install psutil
- pip install daemon

# Usage

Run from commandline as a daemon

Expects a config file.

# Config file

Format:

    command:arg

Commands:

    ps - Check for string <arg> in the ps table

    port - See if something is listening on port <arg>

# Output

{
    'status': 'error|ok',
    'issues': [
        "port: port is not bound '8003'",
        "ps: could not find process 'postgres'"
    ]
}
