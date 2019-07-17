#!/usr/bin/env bash
service nginx start

uwsgi --ini economicserver.ini
