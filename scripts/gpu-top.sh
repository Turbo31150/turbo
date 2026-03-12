#!/bin/bash
# JARVIS GPU Live Monitor v1.0
watch -n 1 "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed --format=csv"
