#!/usr/bin/env bash
# Regenerate the golden test fixtures.
#
#   1. compile + run tools/GenerateFixtures.java  -> tests/data/*.ser
#   2. run the *patched* SerializationDumper jar over each -> tests/data/*.golden
#
# The jar is the byte-for-byte reference DeACED is validated against. It is NOT
# shipped in this repo; point SERDUMP_JAR at your local patched build.
#
# Requirements: a JDK (tested on Temurin 25 LTS) on PATH, and SERDUMP_JAR set.
#
#   SERDUMP_JAR=/path/to/SerializationDumper-PATCHED.jar tools/regen_goldens.sh
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
data="$here/tests/data"
jar="${SERDUMP_JAR:?set SERDUMP_JAR to the patched SerializationDumper jar}"

# Prefer $JAVA_HOME if set, otherwise fall back to javac/java on PATH.
javac_bin="${JAVA_HOME:+$JAVA_HOME/bin/}javac"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"

build="$(mktemp -d)"
trap 'rm -rf "$build"' EXIT

mkdir -p "$data"
"$javac_bin" -d "$build" "$here/tools/GenerateFixtures.java"
( cd "$build" && "$java_bin" GenerateFixtures "$data" )

for ser in "$data"/*.ser; do
    base="$(basename "$ser" .ser)"
    # strip CR so goldens are LF on every platform
    "$java_bin" -jar "$jar" -r "$ser" | tr -d '\r' > "$data/$base.golden"
    echo "regenerated $base.golden"
done
