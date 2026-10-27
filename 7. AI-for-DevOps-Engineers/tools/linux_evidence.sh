#!/usr/bin/env bash
# Linux-only read-only snapshot. Review process command lines before sharing.
set -u
if [[ $(uname -s) != Linux ]]; then echo 'Use a Linux VM or WSL for this exercise' >&2;exit 2;fi
out=${1:-artifacts/linux-evidence}
umask 077
mkdir -p -- "$out"
run() {
  file=$1;shift
  "$@" > "$out/$file" 2> "$out/$file.stderr"
  code=$?
  printf '%s\n' "$code" > "$out/$file.exit"
}
run time.txt date -u +%Y-%m-%dT%H:%M:%SZ
run uptime.txt uptime
run cpu.txt ps -eo pid,ppid,pcpu,pmem,comm --sort=-pcpu
run memory.txt free -h
run disk.txt df -hT
run inodes.txt df -i
run pressure.txt cat /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io
printf 'Evidence captured in %s; inspect .exit files for missing measurements\n' "$out"
