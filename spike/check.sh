#!/usr/bin/env bash
# base-side checker: PR content dir ($1) must contain ok.txt
test -f "${1:-.}/ok.txt" || { echo "CHECK FAILED: ok.txt missing"; exit 1; }
echo "CHECK PASSED"
