#!/bin/sh
# 容器以 root 启动，修正数据卷属主后降权运行（090-25：非 root 运行）。
set -eu
mkdir -p /data
chown -R tableflow:tableflow /data
exec gosu tableflow "$@"
