#!/bin/bash
# Render start command — binds 0.0.0.0 on the platform-provided PORT.
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
