#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh backup_file.sql.gz"
    exit 1
fi

# Decompress
gunzip -c $BACKUP_FILE > /tmp/restore.sql

# Restore database
docker-compose exec -T db psql -U postgres trading_platform < /tmp/restore.sql

rm /tmp/restore.sql

echo "Restore completed"