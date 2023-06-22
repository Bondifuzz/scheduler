#!/bin/sh

autoflake -r ./scheduler --remove-all-unused-imports -i
isort -q ./scheduler
black -q ./scheduler
