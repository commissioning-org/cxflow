#!/usr/bin/env bash
# Quick test harness for the Assistant stubs
# This creates a minimal Laravel-like structure to syntax-check the PHP files.

set -e

echo "=== Syntax checking all Assistant stub PHP files ==="

find .stubs/assistant -name '*.php' -print0 | while IFS= read -r -d '' file; do
    echo -n "Checking: $file ... "
    php -l "$file" 2>&1 | grep -q "No syntax errors" && echo "OK" || echo "FAIL"
done

echo ""
echo "=== Research Agent Demo ==="
echo "Run these commands manually:"
echo ""
echo "  # Clone a repo"
echo "  python -m research_agent clone meilisearch/meilisearch"
echo ""
echo "  # Generate a report"
echo "  python -m research_agent report meilisearch/meilisearch --out reports/meilisearch.md"
echo ""
echo "  # Search for code"
echo "  python -m research_agent search meilisearch/meilisearch 'IndexScheduler'"
echo ""
echo "=== Assistant Command (requires Laravel project) ==="
echo "To use the assistant:run command, copy the stubs into your Laravel project:"
echo ""
echo "  cp -r .stubs/assistant/app/* your-laravel-app/app/"
echo "  cp -r .stubs/assistant/config/* your-laravel-app/config/"
echo ""
echo "Then run:"
echo "  cd your-laravel-app && php artisan assistant:run 'Your prompt here'"
