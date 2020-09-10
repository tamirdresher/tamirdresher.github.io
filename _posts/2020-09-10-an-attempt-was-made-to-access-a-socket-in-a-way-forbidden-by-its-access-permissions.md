---
layout: post
title: "How I fixed the error 'an attempt was made to access a socket in a way forbidden by its access permissions' on my machine"
date: 2020-09-10
---
In the last two days i was fighting the werid situation where i couldn't bind to a specific port on my machine.
All the other ports were fine, but this specific one was just blocked and didn't matter what applicaiton i ran to try to bind to it.

Here are the steps i did until i found the reason:
0. make sure it's not the antivirus or any other security application
1. make sure no other process is using this port by running netstat or [TCPView](https://docs.microsoft.com/en-us/sysinternals/downloads/tcpview)
```
netstat -ano | wsl grep "<port>"
```
2. if anything shows up, kill the process that owns the port
```
kill <PID>
```
3. if this didn't work, reset the machine TCP/IP stack
```
netsh int ip reset
```
4. if you find that anything is was blocked and the message "Access is denied" is shown, follow the steps listed [here](https://davidvielmetter.com/tricks/netsh-int-ip-reset-says-access-denied/) and run the previous step again
5. Reset the machine

