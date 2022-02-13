filename=$(basename -- "$1")
extension="${filename##*.}"
# filename="${fullfile##*/}"
filename="${filename%.*}"
# for debugging: echo "$1" "$filename"_compiled.json $extension
cairo-compile "$1" --output "$filename"_compiled.json

