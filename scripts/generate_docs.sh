#!/bin/sh

rm -rf docs
pdoc3 --html progbg -o docs
mv -f docs/progbg/* docs/
rm -rf docs/progbg
