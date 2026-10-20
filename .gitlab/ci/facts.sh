#!/bin/sh
# Facts about the machine of a CI job: CPU and its x86-64 level, memory, kernel, cgroups,
# privileges and tools. The build job records the build machine (H-1: with GGML_NATIVE ON,
# the build machine sets the floor). The scan job records a job container; the memory and
# offline jobs (F7, F8) are designed from these facts (D-014).
#   sh .gitlab/ci/facts.sh          all facts
#   sh .gitlab/ci/facts.sh --cpu    one line: CPU model and x86-64 level
# A failed check prints its result and the script continues. The only change it makes is one
# empty test cgroup, which it removes at once.
set -u

flags=" $(grep -m 1 '^flags' /proc/cpuinfo | cut -d: -f2) "
has() {
  for flag in "$@"; do
    case "$flags" in *" $flag "*) ;; *) return 1 ;; esac
  done
}
# x86-64 psABI levels, with the flag names of /proc/cpuinfo (pni is SSE3, abm is LZCNT).
level() {
  if ! has cx16 lahf_lm popcnt pni sse4_1 sse4_2 ssse3; then echo x86-64-v1
  elif ! has avx avx2 bmi1 bmi2 f16c fma abm movbe xsave; then echo x86-64-v2
  elif ! has avx512f avx512bw avx512cd avx512dq avx512vl; then echo x86-64-v3
  else echo x86-64-v4
  fi
}
cpu="$(grep -m 1 '^model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')"

if [ "${1:-}" = "--cpu" ]; then
  echo "$cpu ($(level))"
  exit 0
fi

section() { printf '\n## %s\n' "$1"; }
found() { command -v "$1" > /dev/null 2>&1; }

section "CPU"
echo "model: $cpu"
echo "level: $(level) (from the /proc/cpuinfo flags)"
echo "nproc: $(nproc)"
echo "flags:$flags"

section "Memory"
grep -E '^(MemTotal|MemAvailable|SwapTotal):' /proc/meminfo

section "System"
uname -srm
grep -E '^PRETTY_NAME=' /etc/os-release

section "cgroups"
echo "/sys/fs/cgroup: $(stat -fc %T /sys/fs/cgroup 2> /dev/null || echo unknown)"
echo "this process: $(cat /proc/self/cgroup)"
for name in cgroup.controllers cgroup.subtree_control memory.max memory.swap.max; do
  if [ -r "/sys/fs/cgroup/$name" ]; then echo "$name: $(cat "/sys/fs/cgroup/$name")"; fi
done
test_cgroup="/sys/fs/cgroup/floor-facts-$$"
if mkdir "$test_cgroup" 2> /dev/null; then
  echo "child cgroup: can create"
  rmdir "$test_cgroup"
else
  echo "child cgroup: cannot create"
fi

section "Privileges"
grep -E '^(Uid|CapEff|CapBnd|NoNewPrivs|Seccomp):' /proc/self/status
if ! found unshare; then echo "unshare: not found"
elif unshare --net true 2> /dev/null; then echo "unshare --net: works"
else echo "unshare --net: refused"
fi
if [ -d /run/systemd/system ]; then echo "systemd: running"; else echo "systemd: not running"; fi

section "Tools"
for tool in qemu-x86_64 strace python3 crane docker; do
  if found "$tool"; then echo "$tool: $(command -v "$tool")"; else echo "$tool: not found"; fi
done
if found qemu-x86_64; then qemu-x86_64 --version | head -n 1; fi
if found strace; then strace -V | head -n 1; fi
