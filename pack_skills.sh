#!/bin/bash
# 打包 skills 目录为 tar.gz，用于上传到 VPS
# 用法: bash pack_skills.sh
set -e

VERSION=$(date +%Y%m%d%H%M)
cd "$(dirname "$0")"

echo "打包技能 (版本: $VERSION)..."
tar -czf skills.tar.gz -C skills .

echo "{\"version\": \"$VERSION\"}" > skills-version.json

echo "完成！生成文件："
echo "  skills.tar.gz ($(du -h skills.tar.gz | cut -f1))"
echo "  skills-version.json"
echo ""
echo "上传到 VPS:"
echo "  scp skills.tar.gz skills-version.json root@43.128.44.82:/srv/config/"
