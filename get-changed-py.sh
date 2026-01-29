#!/bin/bash

SRC="/Volumes/VMware Shared Folders/cc_mobile on PC/"
DST="/Users/simon/Documents/Projects/cc_mobile/"

rsync -av --update --include='*/' --include='*.py' --exclude='*' "$SRC" "$DST"
