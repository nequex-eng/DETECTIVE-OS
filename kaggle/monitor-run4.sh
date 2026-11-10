#!/bin/bash
# T1 run 3 monitor: polls kernel status every 5 min, up to 200 min.
# Script + log live in the workspace (not /tmp) so a runtime restart
# does not wipe them; recovery handoff can pick up from the log.
export PATH="$HOME/.local/bin:$PATH"
LOG="$HOME/workspace/detective-os/kaggle/run4-monitor.log"
echo "run4 monitor started $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$LOG"
for i in $(seq 1 40); do
  ST=$(kaggle kernels status nequexkaggle/detective-os-t4 2>&1 | head -2)
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) check $i: $ST" >> "$LOG"
  if echo "$ST" | grep -q "COMPLETE"; then echo "COMPLETE detected" >> "$LOG"; break; fi
  if echo "$ST" | grep -q "ERROR"; then echo "ERROR detected" >> "$LOG"; break; fi
  sleep 300
done
echo "run4 monitor ended $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
cat "$LOG"
