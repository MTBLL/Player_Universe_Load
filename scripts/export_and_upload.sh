#!/bin/bash
set -e

PSQL="/opt/homebrew/opt/postgresql@18/bin/psql"
PG_DUMP="/opt/homebrew/opt/postgresql@18/bin/pg_dump"

echo "📦 Exporting local database to SQL dump..."
$PG_DUMP --clean --if-exists fantasy_baseball > /tmp/fantasy_baseball_dump.sql

echo "✅ Exported to /tmp/fantasy_baseball_dump.sql"
echo ""
echo "📊 Dump size:"
ls -lh /tmp/fantasy_baseball_dump.sql
echo ""

# Get Neon connection string from secrets
NEON_URL=$(python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from player_universe_load.secrets import DATABASE_URL
    print(DATABASE_URL)
except:
    print('Error: Could not load DATABASE_URL from player_universe_load/secrets.py')
    exit(1)
")

if [ -z "$NEON_URL" ]; then
    echo "❌ Error: Could not get Neon DATABASE_URL"
    exit 1
fi

echo "🚀 Uploading to Neon database..."
echo "   (This may take 2-3 minutes for initial upload)"
$PSQL "$NEON_URL" < /tmp/fantasy_baseball_dump.sql

echo ""
echo "✅ Upload complete!"
echo ""
echo "🧹 Cleaning up temporary file..."
rm /tmp/fantasy_baseball_dump.sql

echo "✅ Done! Your Neon database is now populated."
