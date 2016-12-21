# servercanary

Version 0.10

Listen on a port and give simple server health check messages.

Returns 200 if ok, 500 if not, with a JSON output.

Particularly useful for AWS ELB health checkers.

# Install

- yum -y install python-devel
- pip install --upgrade psutil daemon netifaces slackclient uptime
- cp ~/servercanary /etc/init.d/
- chmod u+x,g+x /etc/init.d/servercanary
- semanage port -a -t http_port_t -p tcp 8002
- chkconfig --add servercanary
- service servercanary start

# Usage

Run from commandline as a daemon

Expects a config file in /etc/servercanary.cfg.  Another file can be specified with -f commandline option.

Listens on port 8002.  Another port can be specified in the conf file.

PID file is put at /tmp/servercanary.pid.  Another file can be specified in the conf file.

# Config file

Format:

```
[main]
ListenPort: 8005 (default is 8002)
ListenHost: 0.0.0.0 (or maybe localhost) (default is localhost)
PidFile:    /path/to/file.pid (default is /tmp/servercanary.pid)
ShowTime:       yes|no
ShowUptime:     yes|no
GracePeriod:    x (in seconds) (if an error found within grace period of system boot, returns 200 anyways)
                Can be useful for systems that take some time after boot to become ready.
AlertWindow:    x (in seconds) (if an error found within alert window of the last error, no notify sent)

[healthchecks]
command:arg,arg,arg

[notify]
SlackToken: <token>
SlackChannel: Channel Name (exclude the #)
SlackName: <name> (this is the username that it looks like sent the Slack message) (defaults to hostname/ip)
VerboseMessage: yes|no (should the slack message include all errors found?)
```

Commands:

    ps - Check for string <arg> in the ps table

    port - See if something is listening on port <arg>

    pidfile - Check to see if pidfile is valid and running

    service - See if service is running (only works on CentOS/RHEL)

# Output

```
{
    'status': 'error|ok',
    'issues': [
        "port: port is not bound '8003'",
        "ps: could not find process 'postgres'"
    ],
    'datetime': 'date time TZ:timezone',
    'uptime': 'x days hh:mm:ss',
    'inGracePeriod': 'true'
}
```

