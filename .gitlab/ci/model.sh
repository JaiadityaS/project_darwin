#!/bin/sh
# Gets one ggml model into .cache/models (the CI cache) and checks it against the SHA-1 in
# upstream's models/README.md. Downloads only when the file is missing or its hash is wrong.
#   sh .gitlab/ci/model.sh tiny.en
set -eu

name="${1:?usage: sh .gitlab/ci/model.sh <model, for example tiny.en>}"
dir="${MODEL_DIR:-.cache/models}"
file="$dir/ggml-$name.bin"

sha="$(grep -F "| $name " models/README.md | grep -o '[0-9a-f]\{40\}' | head -n 1)"
[ -n "$sha" ] || { echo "model.sh: models/README.md has no SHA-1 for $name" >&2; exit 1; }

mkdir -p "$dir"
if [ -f "$file" ] && echo "$sha  $file" | sha1sum -c --status; then
  echo "model.sh: $file from the cache (sha1 $sha)"
  exit 0
fi

curl -fsSL --retry 3 -o "$file.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$name.bin"
mv "$file.part" "$file"
echo "$sha  $file" | sha1sum -c -
