---
title: "metrics for free: alembic <3 prometheus"
date: 2026-09-03
slug: grafana
tags: [network automation, tooling, release]
summary: "use alembic together with prometheus and grafana to easily collect and visualize metrics about all of the devices in your system"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: prometheus
      url: https://prometheus.io
    - label: grafana
      url: https://grafana.com
---

if you are an alembic user, you probably have a lot of devices to keep
track of. and in that case, you're probably interested in knowing the
status of said devices (like their cpu usage, io read & writes, or the
amount of free memory). `prometheus` is an excellent and popular tool
for collecting such metrics, but it can be cumbersome to set up. you
need to configure it with the ip addresses of all the devices to
monitor, and if anything changes you need to make sure the
configuration is kept up to date. since alembic keeps track of your
inventory (in a backend agnostic way!) it can be used to solve this
problem in a very neat and convenient way. in the following post
we're going to look at how to do this in practice!

# step 1 - importing your data


# step 2 - generating the spec


# step 3 - start prometheus


# step 4 - visualize using grafana


[^1]: this is a footnote
