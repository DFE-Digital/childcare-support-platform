#!/bin/sh
set -e

export SIS_PORT="$FUNCTIONS_CUSTOMHANDLER_PORT"

exec ./sis-query